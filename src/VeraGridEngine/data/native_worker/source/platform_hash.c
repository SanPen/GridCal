/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 * SPDX-License-Identifier: MPL-2.0
 */
#include <stddef.h>
#include <string.h>
#include "platform.h"

static uint32_t rotate_right(uint32_t value, uint32_t count) {
    return (value >> count) | (value << (32U - count));
}

static void transform_block(VgPlatformSha256 *context, const uint8_t block[64]) {
    const uint32_t constants[64] = {
        0x428a2f98U,0x71374491U,0xb5c0fbcfU,0xe9b5dba5U,0x3956c25bU,0x59f111f1U,0x923f82a4U,0xab1c5ed5U,
        0xd807aa98U,0x12835b01U,0x243185beU,0x550c7dc3U,0x72be5d74U,0x80deb1feU,0x9bdc06a7U,0xc19bf174U,
        0xe49b69c1U,0xefbe4786U,0x0fc19dc6U,0x240ca1ccU,0x2de92c6fU,0x4a7484aaU,0x5cb0a9dcU,0x76f988daU,
        0x983e5152U,0xa831c66dU,0xb00327c8U,0xbf597fc7U,0xc6e00bf3U,0xd5a79147U,0x06ca6351U,0x14292967U,
        0x27b70a85U,0x2e1b2138U,0x4d2c6dfcU,0x53380d13U,0x650a7354U,0x766a0abbU,0x81c2c92eU,0x92722c85U,
        0xa2bfe8a1U,0xa81a664bU,0xc24b8b70U,0xc76c51a3U,0xd192e819U,0xd6990624U,0xf40e3585U,0x106aa070U,
        0x19a4c116U,0x1e376c08U,0x2748774cU,0x34b0bcb5U,0x391c0cb3U,0x4ed8aa4aU,0x5b9cca4fU,0x682e6ff3U,
        0x748f82eeU,0x78a5636fU,0x84c87814U,0x8cc70208U,0x90befffaU,0xa4506cebU,0xbef9a3f7U,0xc67178f2U
    };
    uint32_t schedule[64]; uint32_t a,b,c,d,e,f,g,h,index;
    for(index=0;index<16U;++index) schedule[index]=((uint32_t)block[index*4U]<<24)|((uint32_t)block[index*4U+1U]<<16)|((uint32_t)block[index*4U+2U]<<8)|(uint32_t)block[index*4U+3U];
    for(index=16U;index<64U;++index){uint32_t x=schedule[index-15U],y=schedule[index-2U];uint32_t s0=rotate_right(x,7)^rotate_right(x,18)^(x>>3);uint32_t s1=rotate_right(y,17)^rotate_right(y,19)^(y>>10);schedule[index]=schedule[index-16U]+s0+schedule[index-7U]+s1;}
    a=context->state[0];b=context->state[1];c=context->state[2];d=context->state[3];e=context->state[4];f=context->state[5];g=context->state[6];h=context->state[7];
    for(index=0;index<64U;++index){uint32_t sum1=rotate_right(e,6)^rotate_right(e,11)^rotate_right(e,25);uint32_t choice=(e&f)^((~e)&g);uint32_t temporary1=h+sum1+choice+constants[index]+schedule[index];uint32_t sum0=rotate_right(a,2)^rotate_right(a,13)^rotate_right(a,22);uint32_t majority=(a&b)^(a&c)^(b&c);uint32_t temporary2=sum0+majority;h=g;g=f;f=e;e=d+temporary1;d=c;c=b;b=a;a=temporary1+temporary2;}
    context->state[0]+=a;context->state[1]+=b;context->state[2]+=c;context->state[3]+=d;context->state[4]+=e;context->state[5]+=f;context->state[6]+=g;context->state[7]+=h;
}

void vg_platform_sha256_initialize(VgPlatformSha256 *context) {
    const uint32_t initial[8]={0x6a09e667U,0xbb67ae85U,0x3c6ef372U,0xa54ff53aU,0x510e527fU,0x9b05688cU,0x1f83d9abU,0x5be0cd19U};
    if(context!=NULL){memcpy(context->state,initial,sizeof(initial));context->total_bytes=0;context->block_size=0;memset(context->block,0,sizeof(context->block));}
}
int vg_platform_sha256_update(VgPlatformSha256 *context,const uint8_t *bytes,uint64_t size){uint64_t index;if(context==NULL||(bytes==NULL&&size!=0)||UINT64_MAX-context->total_bytes<size)return 0;for(index=0;index<size;++index){context->block[context->block_size++]=bytes[index];if(context->block_size==64U){transform_block(context,context->block);context->block_size=0;}}context->total_bytes+=size;return 1;}
int vg_platform_sha256_finalize(VgPlatformSha256 *context,uint8_t digest[32]){uint64_t bit_count;uint32_t index;if(context==NULL||digest==NULL||context->total_bytes>UINT64_MAX/8U)return 0;bit_count=context->total_bytes*8U;context->block[context->block_size++]=0x80U;if(context->block_size>56U){while(context->block_size<64U)context->block[context->block_size++]=0;transform_block(context,context->block);context->block_size=0;}while(context->block_size<56U)context->block[context->block_size++]=0;for(index=0;index<8U;++index)context->block[63U-index]=(uint8_t)(bit_count>>(index*8U));transform_block(context,context->block);for(index=0;index<8U;++index){digest[index*4U]=(uint8_t)(context->state[index]>>24);digest[index*4U+1U]=(uint8_t)(context->state[index]>>16);digest[index*4U+2U]=(uint8_t)(context->state[index]>>8);digest[index*4U+3U]=(uint8_t)context->state[index];}memset(context,0,sizeof(*context));return 1;}