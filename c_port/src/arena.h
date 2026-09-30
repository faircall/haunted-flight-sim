#ifndef HF_ARENA_H
#define HF_ARENA_H
#include <stddef.h>
#include <stdint.h>

/* One reservation per lifetime. No growing arenas, realloc or hidden fallback.
 * Asset pointers live until unload; frame pointers live until hf_arena_reset.
 * A mark is valid only for its original arena and reset generation. */
typedef struct {
    unsigned char *base;
    size_t capacity, used, peak;
    uint64_t pushes, failures, generation;
    const char *name;
} HFArena;
typedef struct { HFArena *arena; size_t used; uint64_t generation; } HFArenaMark;
typedef struct { void *base; size_t size; HFArena persistent, assets, frame; } HFMemory;

#ifdef _WIN32
#define HF_ARENA_API __declspec(dllexport)
#else
#define HF_ARENA_API
#endif
HF_ARENA_API int hf_memory_init(HFMemory *memory, size_t persistent, size_t assets, size_t frame);
HF_ARENA_API void hf_memory_destroy(HFMemory *memory);
HF_ARENA_API void hf_arena_init(HFArena *arena, void *base, size_t size, const char *name);
HF_ARENA_API void *hf_arena_push(HFArena *arena, size_t count, size_t element_size, size_t alignment, int clear);
HF_ARENA_API HFArenaMark hf_arena_mark(HFArena *arena);
HF_ARENA_API int hf_arena_rewind(HFArenaMark mark);
HF_ARENA_API void hf_arena_reset(HFArena *arena);
#define HF_PUSH(a,T,n) ((T *)hf_arena_push((a),(n),sizeof(T),_Alignof(T),0))
#define HF_PUSH_ZERO(a,T,n) ((T *)hf_arena_push((a),(n),sizeof(T),_Alignof(T),1))
#define HF_MIB(n) ((size_t)(n)*1024u*1024u)
#endif
