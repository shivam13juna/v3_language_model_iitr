# write a quicksort algorithm in python


def quicksort(arr):
    if len(arr) <= 1:
        return arr
    pivot = arr[len(arr) // 2]
    left = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]
    return quicksort(left) + middle + quicksort(right)


def merge_sort(arr):
    if len(arr) <= 1:
        return arr
    mid = len(arr) // 2
    left = merge_sort(arr[:mid])
    right = merge_sort(arr[mid:])
    merged = []
    i = j = 0
    while i < len(left) and j < len(right):
        if left[i] <= right[j]:
            merged.append(left[i])
            i += 1
        else:
            merged.append(right[j])
            j += 1
    merged.extend(left[i:])
    merged.extend(right[j:])
    return merged


def insertion_sort(arr):
    result = arr[:]
    for i in range(1, len(result)):
        key = result[i]
        j = i - 1
        while j >= 0 and result[j] > key:
            result[j + 1] = result[j]
            j -= 1
        result[j + 1] = key
    return result


def heap_sort(arr):
    def heapify(heap, n, i):
        largest = i
        left = 2 * i + 1
        right = 2 * i + 2
        if left < n and heap[left] > heap[largest]:
            largest = left
        if right < n and heap[right] > heap[largest]:
            largest = right
        if largest != i:
            heap[i], heap[largest] = heap[largest], heap[i]
            heapify(heap, n, largest)

    heap = arr[:]
    n = len(heap)
    for i in range(n // 2 - 1, -1, -1):
        heapify(heap, n, i)
    for i in range(n - 1, 0, -1):
        heap[i], heap[0] = heap[0], heap[i]
        heapify(heap, i, 0)
    return heap


# test the quicksort algorithm
if __name__ == "__main__":
    arr = [3, 6, 8, 10, 1, 2, 1]
    print(quicksort(arr))
    print(merge_sort(arr))
    print(insertion_sort(arr))
    print(heap_sort(arr))
