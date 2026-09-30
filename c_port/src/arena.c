#include "arena.h"
#include <string.h>
#include <limits.h>
#if defined(_WIN32)
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#else
#include <sys/mman.h>
#endif

static int add_size(size_t a, size_t b, size_t *out) {
    if (b > SIZE_MAX-a) return 0;
    *out=a+b;
    return 1;
}
void hf_arena_init(HFArena *a, void *base, size_t size, const char *name) {
    *a=(HFArena){.base=base,.capacity=size,.generation=1,.name=name};
}
int hf_memory_init(HFMemory *m, size_t persistent, size_t assets, size_t frame) {
    size_t total;
    *m=(HFMemory){0};
    /* Keep each sub-arena cache-line aligned and reject size overflow. */
    if ((persistent|assets|frame)&63u) return 0;
    if (!add_size(persistent,assets,&total) || !add_size(total,frame,&total) || !total) return 0;
#if defined(_WIN32)
    void *base=VirtualAlloc(NULL,total,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);
    if (!base) return 0;
#else
    void *base=mmap(NULL,total,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
    if (base==MAP_FAILED) return 0;
#endif
    m->base=base; m->size=total;
    hf_arena_init(&m->persistent,base,persistent,"persistent");
    hf_arena_init(&m->assets,(unsigned char *)base+persistent,assets,"assets");
    hf_arena_init(&m->frame,(unsigned char *)base+persistent+assets,frame,"frame");
    return 1;
}
void hf_memory_destroy(HFMemory *m) {
    if (m->base) {
#if defined(_WIN32)
        VirtualFree(m->base,0,MEM_RELEASE);
#else
        munmap(m->base,m->size);
#endif
    }
    *m=(HFMemory){0};
}
void *hf_arena_push(HFArena *a, size_t count, size_t size, size_t alignment, int clear) {
    if (!alignment || (alignment&(alignment-1)) || !a->base || a->used>a->capacity ||
        (size && count>SIZE_MAX/size)) { a->failures++;return NULL; }
    size_t bytes=count*size;
    uintptr_t current=(uintptr_t)a->base+a->used;
    size_t padding=(size_t)((0-current)&(alignment-1));
    size_t remaining=a->capacity-a->used;
    if (padding>remaining || bytes>remaining-padding) { a->failures++;return NULL; }
    void *result=a->base+a->used+padding;
    a->used+=padding+bytes;
    if (a->used>a->peak) a->peak=a->used;
    a->pushes++;
    if (clear && bytes) memset(result,0,bytes);
    return result;
}
HFArenaMark hf_arena_mark(HFArena *a) { return (HFArenaMark){a,a->used,a->generation}; }
int hf_arena_rewind(HFArenaMark mark) {
    HFArena *a=mark.arena;
    if (!a || a->generation!=mark.generation || mark.used>a->used) return 0;
    a->used=mark.used;
    return 1;
}
void hf_arena_reset(HFArena *a) { a->used=0;a->generation++; }
