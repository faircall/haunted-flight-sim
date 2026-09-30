#include "arena.h"
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#define CHECK(x) do { if (!(x)) { fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#x);return 1; } } while(0)
int main(void) {
    HFMemory memory;
    CHECK(hf_memory_init(&memory,HF_MIB(1),HF_MIB(2),HF_MIB(1)));
    CHECK(memory.assets.base==memory.persistent.base+HF_MIB(1));
    HFArena *a=&memory.frame;
    CHECK(HF_PUSH(a,char,3));
    void *aligned=hf_arena_push(a,5,sizeof(double),64,1);
    CHECK(aligned && (uintptr_t)aligned%64==0);
    for (unsigned i=0;i<5;i++) CHECK(((double *)aligned)[i]==0.);
    HFArenaMark mark=hf_arena_mark(a);
    unsigned char *first=HF_PUSH(a,unsigned char,512);
    CHECK(first);memset(first,0xa5,512);
    CHECK(hf_arena_rewind(mark));
    CHECK(HF_PUSH(a,unsigned char,512)==first);
    size_t used=a->used;
    CHECK(!hf_arena_push(a,SIZE_MAX,2,8,0));CHECK(a->used==used);
    CHECK(!hf_arena_push(a,1,1,3,0));CHECK(a->used==used);
    CHECK(!hf_arena_push(a,HF_MIB(2),1,1,0));CHECK(a->used==used);
    CHECK(a->failures==3);
    hf_arena_reset(a);CHECK(a->used==0 && a->peak>=used);
    CHECK(!hf_arena_rewind(mark));
    /* Exhaust exactly: failed pushes must not consume capacity or allocate a
       larger buffer. Reset reuses the same address for arbitrarily many frames. */
    CHECK(HF_PUSH(a,unsigned char,a->capacity)==a->base);
    CHECK(!HF_PUSH(a,char,1));
    uint64_t persistent_pushes=memory.persistent.pushes;
    for (unsigned frame=0;frame<100000;frame++) {
        hf_arena_reset(a);
        CHECK(HF_PUSH(a,unsigned char,65536)==a->base);
    }
    CHECK(memory.persistent.pushes==persistent_pushes);
    hf_memory_destroy(&memory);CHECK(!memory.base);
    CHECK(!hf_memory_init(&memory,SIZE_MAX-63,64,64));
    puts("Arena: alignment, overflow, capacity, mark lifetime and 100000 resets passed.");
    return 0;
}
