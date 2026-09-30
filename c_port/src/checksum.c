#include <stdint.h>
#include <stddef.h>
#ifdef _WIN32
__declspec(dllexport)
#endif
uint64_t hf_hash_rgb(const unsigned char *rgba,size_t bytes) {
    uint64_t hash=UINT64_C(14695981039346656037);
    for(size_t i=0;i<bytes;i++)if((i&3)!=3)hash=(hash^rgba[i])*UINT64_C(1099511628211);
    return hash;
}
