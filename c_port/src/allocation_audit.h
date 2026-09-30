#ifndef HF_ALLOCATION_AUDIT_H
#define HF_ALLOCATION_AUDIT_H
#include <stddef.h>
#include <stdint.h>
typedef struct { uint64_t mallocs,callocs,reallocs,frees;size_t requested_bytes; } HFAllocationCounts;
void hf_allocation_begin(void);
HFAllocationCounts hf_allocation_end(void);
#endif
