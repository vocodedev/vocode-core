# takes an array of predicates and an array
# returns an array of indices whose item matches the predicate, or None if not found
def find_sparse_subarray(target, predicates):
    predicate_index = 0
    subarray_indices = []
    for target_index, item in enumerate(target):
        predicate = predicates[predicate_index]
        if predicate(item):
            subarray_indices.append(target_index)
    
    if len(subarray_indices) == len(predicates):
        return subarray_indices
    else:
        return None

def find_last_sparse_subarray(target, predicates):
    reversed_results = find_sparse_subarray(reversed(target), reversed(predicates))
    if reversed_results == None:
        return None
    return reversed([len(target) -result - 1 for result in reversed_results])
