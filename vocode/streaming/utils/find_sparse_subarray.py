# takes an array of predicates and an array
# returns an array of indices whose item matches the predicate, or None if not found
def find_sparse_subarray(target, predicates):
    predicate_index = 0
    subarray_indices = [None] * len(predicates)

    for target_index, item in enumerate(target):
        if predicate_index >= len(predicates):
            break
        predicate = predicates[predicate_index]
        if predicate(item):
            subarray_indices[predicate_index] = target_index
            predicate_index += 1

    return (
        subarray_indices
        if predicate_index == len(predicates)
        else [None] * len(predicates)
    )


def find_last_sparse_subarray(target, predicates):
    reversed_results = find_sparse_subarray(
        list(reversed(target)), list(reversed(predicates))
    )

    if None in reversed_results:
        return [None] * len(predicates)

    return list(
        reversed(
            [
                len(target) - result - 1
                for result in reversed_results
                if result is not None
            ]
        )
    )
