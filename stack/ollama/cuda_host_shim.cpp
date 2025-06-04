#include <cstdlib>
#include <cstdio>

extern "C" {

typedef enum {
    cudaSuccess = 0,
    cudaErrorMemoryAllocation = 2
} cudaError_t;

cudaError_t cudaMallocHost(void** ptr, size_t size) {
    // printf("[shim] Intercepted cudaMallocHost → malloc fallback (%zu bytes)\n", size);
    int res = posix_memalign(ptr, 4096, size);
    return (res == 0) ? cudaSuccess : cudaErrorMemoryAllocation;
}

cudaError_t cudaFreeHost(void* ptr) {
    // printf("[shim] Intercepted cudaFreeHost → free\n");
    free(ptr);
    return cudaSuccess;
}

}
