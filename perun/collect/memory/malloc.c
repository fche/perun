/*
 * File:        malloc.c
 * Project:     Library for Profiling and Visualization of Memory Consumption
 *              of C/C++ Programs, Bachelor's thesis
 * Date:        29.2.2017
 * Author:      Podola Radim, xpodol06@stud.fit.vutbr.cz
 * Description: File contains implementations of injected allocation functions.
 *
 * Note that this instrumentation was remodelled with great inspiration of the following project
 * (https://github.com/jtolds/malloc_instrumentation). Many thanks to authors for providing
 * a neat solution to the issues with dlsym() or fprintf() allocations (mostly that came with
 * upgrade to Ubuntu 18.04)
 */
#define _GNU_SOURCE
#include <dlfcn.h> //dlsym()
#include <stdio.h>
#include <stdlib.h>
#include <time.h> //clock()
#include <stdbool.h>

#include "backtrace.h"

// File name of the log file
#define LOG_FILE_NAME "MemoryLog"
// 0 - full backtrace log
// 1 - omitting function ad_log() from backtrace log
// 2 - omitting allocation functions from backtrace log
#define CALLS_TO_SKIP 1

static FILE *logFile = NULL;

__thread unsigned int mutex = 0;

int lock_mutex() {
    return __sync_fetch_and_add(&mutex, 1);
}

void unlock_mutex() {
    __sync_fetch_and_sub(&mutex, 1);
}

/* Pointers to temporary and original allocation/free functions */
static void *(*real_malloc)(size_t) = NULL;
static void  (*real_free)(void*) = NULL;
static void *(*real_realloc)(void*, size_t) = NULL;
static void *(*real_calloc)(size_t, size_t)= NULL;
static void *(*real_memalign)(size_t, size_t) = NULL;
static int   (*real_posix_memalign)(void**, size_t, size_t) = NULL;
static void *(*real_valloc)(size_t) = NULL;
static void *(*real_aligned_alloc)(size_t, size_t) = NULL;

/*
GCC destructor attribute provides finalizing function which close log file properly
after main program's execution finished
*/
__attribute__((destructor)) void finalize (void){
    if(logFile != NULL){
        fprintf(logFile, "EXIT %fs\n", clock() / (double)CLOCKS_PER_SEC);
        fclose(logFile);
    }
}

/*
Prepare the log file to use it for logging
*/
void init_log_file(){
    lock_mutex();

    if(!logFile) {
       logFile = fopen(LOG_FILE_NAME, "w");
       if(logFile == NULL){
          fprintf(stderr, "error: fopen()\n");
          exit(EXIT_FAILURE);
       }
    }

    unlock_mutex();
}

/*
Writes the allocation metadata to the log file
*/
void ad_log(char *allocator, size_t size, void *ptr){
    lock_mutex();

    fprintf(logFile, "time %fs\n", clock() / (double)CLOCKS_PER_SEC);
    fprintf(logFile, "%s %luB %li\n", allocator, (unsigned long) size, (long int)ptr);
    backtrace(logFile, CALLS_TO_SKIP);
    fprintf(logFile, "\n");

    unlock_mutex();
}

//Redefinitions of the standard allocation functions
void *malloc(size_t size){
    if(!real_malloc){
        real_malloc = dlsym(RTLD_NEXT, "malloc");
        if(real_malloc == NULL){
            fprintf(stderr, "error: dlsym() malloc\n");
            exit(EXIT_FAILURE);
        }
        init_log_file();
    }

    void *ptr = real_malloc(size);

    if(!mutex && ptr != NULL){
        ad_log("malloc", size, ptr);
    }

    return ptr;
}

void free(void *ptr){
    if(!real_free){
        real_free = dlsym(RTLD_NEXT, "free");
        if(real_free == NULL){
            fprintf(stderr, "error: dlsym() free\n");
            exit(EXIT_FAILURE);
        }
        init_log_file();
    }

    real_free(ptr);

    if(!mutex){
        ad_log("free", 0, ptr);
    }
}

void *realloc(void *ptr, size_t size){
    void *old_ptr = NULL;
    if(!real_realloc){
        real_realloc = dlsym(RTLD_NEXT, "realloc");
        if(real_realloc == NULL){
            fprintf(stderr, "error: dlsym() realloc\n");
            exit(EXIT_FAILURE);
        }
        init_log_file();
    }
    old_ptr = ptr;
    void *nptr = real_realloc(ptr, size);

    if(!mutex && nptr != NULL){
        ad_log("realloc", size, nptr);
        ad_log("free", 0, old_ptr);
    }

    return nptr;
}

void *calloc(size_t nmemb, size_t size){
    if(!real_calloc){
        real_calloc = dlsym(RTLD_NEXT, "calloc");
        if(real_calloc == NULL){
            fprintf(stderr, "error: dlsym() calloc\n");
            exit(EXIT_FAILURE);
        }
        init_log_file();
    }

    void *ptr = real_calloc(nmemb, size);

    if(!mutex && ptr != NULL){
        ad_log("calloc", size*nmemb, ptr);
    }

    return ptr;
}

void *memalign(size_t alignment, size_t size){
    if(!real_memalign){
        real_memalign = dlsym(RTLD_NEXT, "memalign");
        if(real_memalign == NULL){
            fprintf(stderr, "error: dlsym() memalign\n");
            exit(EXIT_FAILURE);
        }
        init_log_file();
    }

    void *ptr = real_memalign(alignment, size);

    if(!mutex && ptr != NULL){
        ad_log("memalign", size, ptr);
    }

    return ptr;
}

int posix_memalign(void** memptr, size_t alignment, size_t size){
    if(!real_posix_memalign){
        real_posix_memalign = dlsym(RTLD_NEXT, "posix_memalign");
        if(real_posix_memalign == NULL){
            fprintf(stderr, "error: dlsym() posix_memalign\n");
            exit(EXIT_FAILURE);
        }
        init_log_file();
    }

    int ret = real_posix_memalign(memptr, alignment, size);

    if(!mutex && ret == 0){
        ad_log("posix_memalign", size, *memptr);
    }

    return ret;
}

void *valloc(size_t size){
    if(!real_valloc){
        real_valloc = dlsym(RTLD_NEXT, "valloc");
        if(real_valloc == NULL){
            fprintf(stderr, "error: dlsym() valloc\n");
            exit(EXIT_FAILURE);
        }
        init_log_file();
    }

    void *ptr = real_valloc(size);

    if(!mutex && ptr != NULL){
        ad_log("valloc", size, ptr);
    }

    return ptr;
}

void *aligned_alloc(size_t alignment, size_t size){
    if(!real_aligned_alloc){
        real_aligned_alloc = dlsym(RTLD_NEXT, "aligned_alloc");
        if(real_aligned_alloc == NULL){
            fprintf(stderr, "error: dlsym() aligned_alloc\n");
            exit(EXIT_FAILURE);
        }
        init_log_file();
    }

    void *ptr = real_aligned_alloc(alignment, size);

    if(!mutex && ptr != NULL){
        ad_log("aligned_alloc", size, ptr);
    }

    return ptr;
}