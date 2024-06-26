#!/usr/bin/env python3

""" This entry knows how to make other entries.
"""

from copy import deepcopy
import logging
import os

def walk(__entry__):
    """An internal recursive generator not to be called directly
    """

    ak = __entry__.get_kernel()
    assert ak != None, "__entry__'s kernel should be defined"
    collection_own_name = __entry__.get_name()


    logging.debug(f"collection({collection_own_name}): yielding the collection itself")
    yield __entry__

    logging.debug(f"collection({collection_own_name}): walking contained_entries:")
    contained_entries = __entry__.get('contained_entries', {})
    for entry_name in contained_entries:
        relative_entry_path = contained_entries[entry_name]
        logging.debug(f"collection({collection_own_name}): mapping {entry_name} to relative_entry_path={relative_entry_path}")

        contained_entry = ak.bypath(path=__entry__.get_path(relative_entry_path), name=entry_name, container=__entry__)

        # Have to resort to duck typing to avoid triggering dependencies by testing if contained_entry.can('walk'):
        if 'contained_entries' in contained_entry.own_data():
            logging.debug(f"collection({collection_own_name}): recursively walking collection {entry_name}...")
            yield from walk(contained_entry)
        else:
            logging.debug(f"collection({collection_own_name}): yielding non-collection {entry_name}")
            yield contained_entry


def attached_entry(entry_path=None, own_data=None, generated_name_prefix=None, __entry__=None):
    """Create a new entry with the given name and attach it to this collection

Usage examples :
                axs work_collection , attached_entry ultimate_answer ---='{"answer":42}' , save
    """

    return __entry__.get_kernel().fresh_entry(container=__entry__, entry_path=entry_path, own_data=own_data, generated_name_prefix=generated_name_prefix)


def byname(entry_name, __entry__):
    """Fetch an entry by name
    """

    for candidate_entry in walk(__entry__):
        if candidate_entry.get_name() == entry_name:
            return candidate_entry
    return None



class FilterPile:

    def __init__(self, conditions, context):

        def parse_condition(condition, context):

            if type(condition)==list:   # pre-parsed equality
                key_path, val = condition
                op = '='
                comparison_lambda   = lambda x: x==val

            else:   # assuming a string that needs to be parsed (even if a tag)
                import re
                from function_access import to_num_or_not_to_num

                binary_op_match = re.match('([\w\.\-]*\w)(:=|\?=|===|==|=|!==|!=|<>|<=|>=|<|>|:|!:)(.*)$', condition)
                if binary_op_match:
                    key_path    = binary_op_match.group(1)
                    op          = binary_op_match.group(2)
                    pre_val     = binary_op_match.group(3)
                    val         = to_num_or_not_to_num(pre_val)

                    if op in (':=',):           # auto-split
                        op = '='
                        pre_val = pre_val.split(':')
                        val     = [ to_num_or_not_to_num(x) for x in pre_val ]
                        comparison_lambda   = lambda x: x==val
                    elif op in ('?=',):         # optional/selective match
                        comparison_lambda   = lambda x: x==val
                    elif op in ('=', '=='):     # with auto-conversion to numbers
                        op = '='
                        comparison_lambda   = lambda x: x==val
                    elif op in ('===',):        # no auto-conversion
                        op = '='
                        comparison_lambda   = lambda x: x==pre_val
                        val                 = pre_val
                    elif op in ('<>', '!='):    # with auto-conversion to numbers
                        comparison_lambda   = lambda x: x!=val
                    elif op in ('!==',):        # no auto-conversion
                        comparison_lambda   = lambda x: x!=pre_val
                        val                 = pre_val
                    elif op=='<' and len(pre_val)>0:
                        comparison_lambda   = lambda x: x!=None and x<val
                    elif op=='>' and len(pre_val)>0:
                        comparison_lambda   = lambda x: x!=None and x>val
                    elif op=='<=' and len(pre_val)>0:
                        comparison_lambda   = lambda x: x!=None and x<=val
                    elif op=='>=' and len(pre_val)>0:
                        comparison_lambda   = lambda x: x!=None and x>=val
                    elif op==':' and len(pre_val)>0:
                        comparison_lambda   = lambda x: type(x)==list and val in x
                    elif op=='!:' and len(pre_val)>0:
                        comparison_lambda   = lambda x: type(x)==list and val not in x
                    else:
                        raise SyntaxError(f"Could not parse the condition '{condition}' in {context}")
                else:
                    unary_op_match = re.match('([\w\.]*\w)(\.|!\.|\?|\+|-)$', condition)
                    if unary_op_match:
                        key_path    = unary_op_match.group(1)
                        op          = unary_op_match.group(2)
                        val         = None
                        if op=='.':               # path exists
                            comparison_lambda   = lambda x: x is not None
                        elif op=='!.':            # path does not exist
                            comparison_lambda   = lambda x: x is None
                        elif op=='+':             # computes to True
                            op, val = '=', True
                            comparison_lambda   = lambda x: bool(x)
                        elif op=='-':             # computes to False
                            op, val = '=', False
                            comparison_lambda   = lambda x: not bool(x)
                        else:
                            raise SyntaxError(f"Could not parse the condition '{condition}' in {context}")
                    else:
                        tag_match = re.match('([!^-])?(\w+)$', condition)
                        if tag_match:
                            key_path    = 'tags'
                            val         = tag_match.group(2)
                            if tag_match.group(1):
                                op = "tag-"
                                comparison_lambda   = lambda x: type(x)!=list or val not in x
                            else:
                                op = "tag+"
                                comparison_lambda   = lambda x: type(x)==list and val in x
                        else:
                            raise SyntaxError(f"Could not parse the condition '{condition}' in {context}")

            return key_path, op, val, comparison_lambda


        self.conditions    = conditions if type(conditions)==list else conditions.split(',')
        self.context       = context
        self.posi_tag_set  = set()
        self.posi_val_dict = {}
        self.opti_val_dict = {}
        self.mentioned_set = set()
        self.filter_list   = []

        # parsing the Query:
        for condition in self.conditions:
            if condition in (None, ""): continue

            key_path, op, val, comparison_lambda = parse_condition( condition, self.context )
            self.mentioned_set.add( key_path )

            if op=='=':
                self.posi_val_dict[key_path] = val
            elif op=='?=':
                self.opti_val_dict[key_path] = val
            elif op=='tag+':
                self.posi_tag_set.add( val )

            self.filter_list.append( (key_path, op, val, comparison_lambda, key_path.split('.')) )


    def matches_entry(self, candidate_entry, parent_recursion):

        candidate_still_ok = True
        for key_path, op, val, query_comparison_lambda, split_key_path in self.filter_list:
            if not query_comparison_lambda( candidate_entry.dig(split_key_path, safe=True, parent_recursion=parent_recursion) ):
                candidate_still_ok = False
                break
        return candidate_still_ok


def all_byquery(query, template=None, parent_recursion=False, __entry__=None):
    """Returns a list of ALL entries matching the query.
        Empty list if nothing matched.

Usage examples :
                axs all_byquery onnx_model
                axs all_byquery python_package,package_name=pillow
                axs all_byquery onnx_model "#{model_name}# : #{file_name}#"
                axs all_byquery python_package "Python package #{package_name}# version #{package_version}#"
                axs all_byquery tags. "tags=#{tags}#"
    """
    assert __entry__ != None, "__entry__ should be defined"

    parsed_query        = FilterPile( query, "Query" )

    # trying to match the Query in turn against each existing and walkable entry, gathering them all:
    matched_entries = []
    for candidate_entry in walk(__entry__):
        if parsed_query.matches_entry( candidate_entry, parent_recursion ):
            matched_entries.append( candidate_entry if template is None else str(candidate_entry.substitute(template)) )

    return matched_entries if template is None else "\n".join( matched_entries )


def byquery(query, produce_if_not_found=True, parent_recursion=False, __entry__=None):
    """Fetch an entry by query.
        If the query returns nothing on the first pass, but matching _producer_rules are defined,
        apply the matching producer_rule and return its output.

Usage examples :
                axs byquery python_package,package_name=numpy , get_path
                axs byquery python_package,package_name=numpy,package_version=1.16.4 , get_metadata --header_name=Version
                axs byquery shell_tool,tool_name=wget
            # the query given as an explicit list of query_conditions
                axs byquery axs byquery --:=count:romance:^french
                axs byquery "--,=count,romance,language!=French"
    """
    assert __entry__ != None, "__entry__ should be defined"

    parsed_query        = FilterPile( query, "Query" )

    # trying to match the Query in turn against each existing and walkable entry, first match returns:
    for candidate_entry in walk(__entry__):
        if parsed_query.matches_entry( candidate_entry, parent_recursion ):
            return candidate_entry

    # if a matching entry does not exist, see if we can produce it with a matching Rule
    if produce_if_not_found and len(parsed_query.posi_tag_set):
        logging.warning(f"[{__entry__.get_name()}] byquery({query}) did not find anything, but there are tags: {parsed_query.posi_tag_set} , trying to find a producer...")

        matched_rules = []
        for advertising_entry in walk(__entry__):
            for unprocessed_rule in advertising_entry.own_data().get('_producer_rules', []):        # block processing some params until they are really needed
                parsed_rule     = FilterPile( advertising_entry.nested_calls( unprocessed_rule[0] ), f"Entry: {advertising_entry.get_name()}" )

                if parsed_rule.posi_tag_set.issubset(parsed_query.posi_tag_set):  # FIXME:  parsed_rule.posi_tag_set should include it
                    qr_conditions_ok  = True

                    # first matching rule's conditions against query's values:
                    for key_path, op, rule_val, rule_comparison_lambda, _ in parsed_rule.filter_list:

                        if op=='tag+': continue     # we have matched them directly above

                        # we allow (only) equalities on the rule side not to have a match on the query side
                        if (key_path in parsed_query.posi_val_dict):    # does the query contain a specific value for this rule condition's key_path?
                            qr_conditions_ok = rule_comparison_lambda( parsed_query.posi_val_dict[key_path] )       # if so, use this value in evaluating this rule condition
                        else:
                            qr_conditions_ok = (((op=='?=') and (key_path not in parsed_query.mentioned_set)) or    # ignore optional(selective) matches
                                                ((op=='!.') and (key_path not in parsed_query.mentioned_set)) or
                                                ((op=='=') and (key_path in parsed_query.mentioned_set)))           # otherwise if this rule condition sets a value, the query should have a corresponding condition to check (later) 

                        if not qr_conditions_ok: break

                    if qr_conditions_ok:
                        # then matching query's conditions against rule's values:
                        for key_path, op, query_val, query_comparison_lambda, _ in parsed_query.filter_list:

                            if op=='tag+': continue     # we have matched them directly above

                            # we allow (only) equalities on the query side not to have a match on the rule side
                            if (key_path in parsed_rule.posi_val_dict): # does the rule contain a specific value for this query condition's key_path?
                                qr_conditions_ok = query_comparison_lambda( parsed_rule.posi_val_dict[key_path] )   # if so, use this value in evaluating this query condition
                            else:
                                qr_conditions_ok = (op=='=')                                                        # otherwise this query condition must set a value

                            if not qr_conditions_ok: break

                    if qr_conditions_ok:
                        matched_rules.append( (unprocessed_rule, advertising_entry, parsed_rule) )

        logging.warning(f"[{__entry__.get_name()}] A total of {len(matched_rules)} matched rules found.\n")

        match_idx = 0
        for unprocessed_rule, advertising_entry, parsed_rule in sorted( matched_rules, key = lambda x: len(x[0][0]), reverse=True):
            match_idx += 1  # matches are 1-based
            logging.warning(f"Matched Rule #{match_idx}/{len(matched_rules)}: {unprocessed_rule[0]} from Entry '{advertising_entry.get_name()}'...")

            rule_vector         = advertising_entry.nested_calls(unprocessed_rule)
            producer_pipeline   = rule_vector[1]
            extra_params        = rule_vector[2] if len(rule_vector)>2 else {}
            export_params       = rule_vector[3] if len(rule_vector)>3 else []

            cumulative_params = advertising_entry.slice( *export_params )   # default slice
            cumulative_params.update( parsed_rule.opti_val_dict )           # optional matches on top (may override some defaults)
            cumulative_params.update( deepcopy( extra_params ) )            # extra_params on top (may override some defaults)
            cumulative_params.update( parsed_rule.posi_val_dict )           # rules on top (may override some defaults)
            cumulative_params.update( parsed_query.posi_val_dict )          # query on top (may override some defaults)
            cumulative_params["tags"] = list(parsed_query.posi_tag_set)     # FIXME:  parsed_rule.posi_tag_set should include it
            logging.warning(f"Pipeline: {producer_pipeline}, Cumulative params: {cumulative_params}")

            new_entry = advertising_entry.execute(producer_pipeline, cumulative_params)

            if new_entry:
                logging.warning(f"Matched Rule #{match_idx}/{len(matched_rules)} produced a result.\n")
                return new_entry
            else:
                logging.warning(f"Matched Rule #{match_idx}/{len(matched_rules)} didn't produce a result, {len(matched_rules)-match_idx} more matched rules to try...\n")

    else:
        logging.debug(f"[{__entry__.get_name()}] byquery({query}) did not find anything, and no matching _producer_rules => returning None")
        return None


def add_entry_path(new_entry_path, new_entry_name=None, __entry__=None):
    """Add a new entry to the collection given the path
    """
    assert __entry__ != None, "__entry__ should be defined"

    trimmed_new_entry_path  = __entry__.trim_path( new_entry_path )
    new_entry_name          = new_entry_name or os.path.basename( trimmed_new_entry_path )
    existing_rel_path       = __entry__.dig(['contained_entries', new_entry_name], safe=True)

    if existing_rel_path:
        if existing_rel_path == trimmed_new_entry_path:
            logging.warning(f"The entry {existing_rel_path} has already been attached to the {__entry__.get_name()} collection, skipping")
        else:
            raise(KeyError(f"There was already another entry named {new_entry_name} with path {existing_rel_path}, remove it first"))
    else:
        __entry__.plant(['contained_entries', new_entry_name], trimmed_new_entry_path)
        return __entry__.save()


def remove_entry_name(old_entry_name, __entry__):

    contained_entries       = __entry__.pluck(['contained_entries', old_entry_name])
    return __entry__.save()


if __name__ == '__main__':

    print("Unfortunately this entry cannot be tested separately from the framework")

