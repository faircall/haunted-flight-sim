#include "allocation_audit.h"
#include "arena.h"
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#define CHECK(x) do { if (!(x)) { fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#x);return 1; } } while(0)
int main(void) {
    /* Build this test without allocation builtins: the optimizer must not fold
     * away the deliberate heap traffic used to verify the linker wrappers. */
    hf_allocation_begin();
    void *a=malloc(17),*b=calloc(6,7);
    CHECK(a && b);memset(a,3,17);
    a=realloc(a,39);CHECK(a);free(a);free(b);
    HFAllocationCounts counts=hf_allocation_end();
    CHECK(counts.mallocs==1 && counts.callocs==1 && counts.reallocs==1);
    CHECK(counts.frees==2 && counts.requested_bytes==98);
    HFMemory memory;CHECK(hf_memory_init(&memory,HF_MIB(1),HF_MIB(1),HF_MIB(1)));
    hf_allocation_begin();
    for (int i=0;i<10000;i++) {
        hf_arena_reset(&memory.frame);
        unsigned char *p=HF_PUSH(&memory.frame,unsigned char,4096);
        CHECK(p);memset(p,i,4096);
    }
    counts=hf_allocation_end();
    CHECK(!counts.mallocs && !counts.callocs && !counts.reallocs && !counts.frees);
    CHECK(!counts.requested_bytes);
    hf_memory_destroy(&memory);
    puts("Allocation audit: deliberate heap traffic detected; 10000 arena frames allocate no heap.");
    return 0;
}
