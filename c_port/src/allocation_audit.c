/* GNU linker wrapping covers our executable and the statically linked raylib.
 * It cannot intercept allocations internal to external GPU/OS DLLs. */
#include "allocation_audit.h"
#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
static DWORD owner;
#define IN_SCOPE (active && GetCurrentThreadId()==owner)
#else
#define IN_SCOPE active
#endif
void *__real_malloc(size_t);
void *__real_calloc(size_t,size_t);
void *__real_realloc(void *,size_t);
void __real_free(void *);
/* Avoid compiler-emulated TLS here: its first access itself calls malloc.
 * This scope belongs to the render thread; other threads are excluded. */
static int active;
static HFAllocationCounts counts;
void hf_allocation_begin(void) {
#ifdef _WIN32
    owner=GetCurrentThreadId();
#endif
    counts=(HFAllocationCounts){0};active=1;
}
HFAllocationCounts hf_allocation_end(void) { active=0;return counts; }
void *__wrap_malloc(size_t n) {
    if(IN_SCOPE) { counts.mallocs++;counts.requested_bytes+=n; }
    return __real_malloc(n);
}
void *__wrap_calloc(size_t n,size_t size) {
    if(IN_SCOPE) { counts.callocs++;counts.requested_bytes+=n*size; }
    return __real_calloc(n,size);
}
void *__wrap_realloc(void *p,size_t n) {
    if(IN_SCOPE) { counts.reallocs++;counts.requested_bytes+=n; }
    return __real_realloc(p,n);
}
void __wrap_free(void *p) { if(IN_SCOPE && p)counts.frees++;__real_free(p); }
