/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 * SPDX-License-Identifier: MPL-2.0
 */
#include <math.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include "adapter_iec_ese.h"
#include "protocol.h"
#include "platform.h"

#define REQUIRE(R,N) do{if((uint64_t)(R)<(uint64_t)(N))return VG_NATIVE_BAD_PAYLOAD;}while(0)
#define READ_U32(P,R,V) do{REQUIRE((R),4);memcpy(&(V),(P),4);(P)+=4;(R)-=4;}while(0)
#define APPEND(B,C,L,S,N) do{if((C)+(uint64_t)(N)>(L))return VG_NATIVE_BAD_PAYLOAD;memcpy((B)+(C),(S),(size_t)(N));(C)+=(uint64_t)(N);}while(0)
#define APPEND_U32(B,C,L,V) do{uint32_t value_=(uint32_t)(V);APPEND((B),(C),(L),&value_,4);}while(0)
#define APPEND_TEXT(B,C,L,T) do{const char *text_=(T)==NULL?"":(T);uint64_t size_=0;if(!vg_native_bounded_text_size(text_,16777216U,&size_))return VG_NATIVE_ABI_FAILURE;APPEND_U32((B),(C),(L),size_);APPEND((B),(C),(L),text_,size_);}while(0)
static int call_ok(const char *error){return error==NULL||error[0]==0;}
static int add_size(uint64_t left,uint64_t right,uint64_t *result){if(result==NULL||UINT64_MAX-left<right)return 0;*result=left+right;return 1;}
static int flat_count(const VgIecEseAdapter *adapter,int inputs,uint32_t *count){
    int32_t index,total=inputs?adapter->info->input_count:adapter->info->output_count;uint64_t scalars=0;
    for(index=0;index<total;++index){int32_t width=inputs?adapter->info->inputs[index].width:adapter->info->outputs[index].width;
        if(width<=0||!add_size(scalars,(uint64_t)width,&scalars)||scalars>adapter->limits.maximum_scalar_slots||scalars>UINT32_MAX)return 0;}
    *count=(uint32_t)scalars;return 1;
}
static void destroy_instance(EseInstance *instance){if(instance==NULL)return;free(instance->identifier);free(instance);}
void vg_iec_ese_initialize_adapter(VgIecEseAdapter *adapter) {
    if (adapter != NULL) {
        memset(adapter, 0, sizeof(*adapter));
    } else {
        return;
    }
}

int vg_iec_ese_bind(const VgPlatformLibrary *library,
                    const VgNativeAdapterLimits *limits,
                    VgIecEseAdapter *adapter) {
    EseGetInfo get_info;
    if (library == NULL || limits == NULL || adapter == NULL) {
        return VG_NATIVE_BAD_PAYLOAD;
    } else {
        vg_iec_ese_initialize_adapter(adapter);
    }
    get_info = (EseGetInfo)vg_platform_library_symbol(library, "Model_GetInfo");
    adapter->create = (EseCreate)vg_platform_library_symbol(library, "Model_Instance");
    adapter->check_parameters = (EseCall)vg_platform_library_symbol(
        library, "Model_CheckParameters"
    );
    adapter->initialize = (EseCall)vg_platform_library_symbol(library, "Model_Initialize");
    adapter->outputs = (EseOutputs)vg_platform_library_symbol(library, "Model_Outputs");
    adapter->update = (EseCall)vg_platform_library_symbol(library, "Model_Update");
    adapter->terminate = (EseCall)vg_platform_library_symbol(library, "Model_Terminate");
    if (get_info == NULL || adapter->create == NULL || adapter->check_parameters == NULL
            || adapter->initialize == NULL || adapter->outputs == NULL
            || adapter->update == NULL || adapter->terminate == NULL
            || vg_platform_library_symbol(library, "Model_Loadflow") == NULL
            || vg_platform_library_symbol(library, "Model_Derivatives") == NULL) {
        vg_iec_ese_destroy(adapter);
        return VG_NATIVE_ABI_FAILURE;
    } else {
        adapter->limits = *limits;
        adapter->info = get_info();
        adapter->instances = (EseInstance **)calloc(
            limits->maximum_instances, sizeof(EseInstance *)
        );
    }
    if (adapter->info == NULL || adapter->instances == NULL) {
        vg_iec_ese_destroy(adapter);
        return VG_NATIVE_ABI_FAILURE;
    } else {
        return VG_NATIVE_OK;
    }
}
int vg_iec_ese_copy_model_info(VgIecEseAdapter *adapter,uint8_t **payload,uint64_t *payload_size){
    const EseModelInfo *info;uint8_t *buffer;uint64_t cursor=0,scalars=0;int direction;int32_t index;
    if(adapter==NULL||payload==NULL||payload_size==NULL)return VG_NATIVE_BAD_PAYLOAD;info=adapter->info;
    if(memcmp(info->release,"\x01\x00\x00\x00",4)!=0||!isfinite(info->sample_time)||info->sample_time<=0.0||info->mode<1||info->mode>3||info->loadflow>1||info->input_count<0||(uint32_t)info->input_count>adapter->limits.maximum_ports||info->output_count<0||(uint32_t)info->output_count>adapter->limits.maximum_ports||info->parameter_count<0||(uint32_t)info->parameter_count>adapter->limits.maximum_parameters||info->continuous_states<0||info->miscellaneous_bytes<0||(uint64_t)info->continuous_states>adapter->limits.maximum_state_scalars)return VG_NATIVE_ABI_FAILURE;
    buffer=(uint8_t*)malloc((size_t)adapter->limits.maximum_frame_bytes);if(buffer==NULL)return VG_NATIVE_ABI_FAILURE;
    {uint8_t interface_record[4]={3,0,0,0};uint8_t sample_record[4]={1,info->mode,info->loadflow,0};
    APPEND(buffer,cursor,adapter->limits.maximum_frame_bytes,interface_record,4);APPEND(buffer,cursor,adapter->limits.maximum_frame_bytes,info->release,4);
    APPEND_TEXT(buffer,cursor,adapter->limits.maximum_frame_bytes,info->name);APPEND_TEXT(buffer,cursor,adapter->limits.maximum_frame_bytes,info->version);APPEND_TEXT(buffer,cursor,adapter->limits.maximum_frame_bytes,info->description);APPEND_TEXT(buffer,cursor,adapter->limits.maximum_frame_bytes,info->version_control);APPEND_TEXT(buffer,cursor,adapter->limits.maximum_frame_bytes,info->general);APPEND_TEXT(buffer,cursor,adapter->limits.maximum_frame_bytes,info->created);APPEND_TEXT(buffer,cursor,adapter->limits.maximum_frame_bytes,info->creator);APPEND_TEXT(buffer,cursor,adapter->limits.maximum_frame_bytes,info->modified_date);APPEND_TEXT(buffer,cursor,adapter->limits.maximum_frame_bytes,info->modified_by);APPEND_TEXT(buffer,cursor,adapter->limits.maximum_frame_bytes,info->modified_comment);APPEND_TEXT(buffer,cursor,adapter->limits.maximum_frame_bytes,info->modified_history);APPEND_TEXT(buffer,cursor,adapter->limits.maximum_frame_bytes,info->generated);APPEND_TEXT(buffer,cursor,adapter->limits.maximum_frame_bytes,info->solver);APPEND(buffer,cursor,adapter->limits.maximum_frame_bytes,&info->sample_time,8);APPEND(buffer,cursor,adapter->limits.maximum_frame_bytes,&info->sample_time,8);APPEND(buffer,cursor,adapter->limits.maximum_frame_bytes,sample_record,4);}
    for(direction=0;direction<2;++direction){int32_t count=direction==0?info->input_count:info->output_count;if(count>0&&((direction==0&&info->inputs==NULL)||(direction==1&&info->outputs==NULL))){free(buffer);return VG_NATIVE_ABI_FAILURE;}APPEND_U32(buffer,cursor,adapter->limits.maximum_frame_bytes,count);for(index=0;index<count;++index){const EseSignal *signal=direction==0?&info->inputs[index]:&info->outputs[index];uint8_t tag[4]={9,0,0,0};if(signal->width<=0||!add_size(scalars,(uint64_t)signal->width,&scalars)||scalars>adapter->limits.maximum_scalar_slots){free(buffer);return VG_NATIVE_ABI_FAILURE;}APPEND_TEXT(buffer,cursor,adapter->limits.maximum_frame_bytes,signal->name);APPEND_TEXT(buffer,cursor,adapter->limits.maximum_frame_bytes,"");APPEND_TEXT(buffer,cursor,adapter->limits.maximum_frame_bytes,"");APPEND_TEXT(buffer,cursor,adapter->limits.maximum_frame_bytes,signal->path);APPEND(buffer,cursor,adapter->limits.maximum_frame_bytes,tag,4);APPEND_U32(buffer,cursor,adapter->limits.maximum_frame_bytes,signal->width);APPEND_U32(buffer,cursor,adapter->limits.maximum_frame_bytes,0);}}
    if(info->parameter_count>0&&info->parameters==NULL){free(buffer);return VG_NATIVE_ABI_FAILURE;}APPEND_U32(buffer,cursor,adapter->limits.maximum_frame_bytes,info->parameter_count);
    for(index=0;index<info->parameter_count;++index){const EseParameter *parameter=&info->parameters[index];uint8_t record[4]={9,0,0,0},bounds[4]={1,1,0,0},tag=9;if(!isfinite(parameter->default_value)||!isfinite(parameter->minimum_value)||!isfinite(parameter->maximum_value)){free(buffer);return VG_NATIVE_ABI_FAILURE;}APPEND_TEXT(buffer,cursor,adapter->limits.maximum_frame_bytes,parameter->name);APPEND_TEXT(buffer,cursor,adapter->limits.maximum_frame_bytes,"");APPEND_TEXT(buffer,cursor,adapter->limits.maximum_frame_bytes,parameter->description);APPEND_TEXT(buffer,cursor,adapter->limits.maximum_frame_bytes,parameter->unit);APPEND(buffer,cursor,adapter->limits.maximum_frame_bytes,record,4);APPEND(buffer,cursor,adapter->limits.maximum_frame_bytes,&tag,1);APPEND(buffer,cursor,adapter->limits.maximum_frame_bytes,&parameter->default_value,8);APPEND(buffer,cursor,adapter->limits.maximum_frame_bytes,bounds,4);APPEND(buffer,cursor,adapter->limits.maximum_frame_bytes,&tag,1);APPEND(buffer,cursor,adapter->limits.maximum_frame_bytes,&parameter->minimum_value,8);APPEND(buffer,cursor,adapter->limits.maximum_frame_bytes,&tag,1);APPEND(buffer,cursor,adapter->limits.maximum_frame_bytes,&parameter->maximum_value,8);}
    APPEND_U32(buffer,cursor,adapter->limits.maximum_frame_bytes,info->continuous_states);APPEND_U32(buffer,cursor,adapter->limits.maximum_frame_bytes,info->miscellaneous_bytes);APPEND_U32(buffer,cursor,adapter->limits.maximum_frame_bytes,0);APPEND_U32(buffer,cursor,adapter->limits.maximum_frame_bytes,0);APPEND_U32(buffer,cursor,adapter->limits.maximum_frame_bytes,0);*payload=buffer;*payload_size=cursor;return VG_NATIVE_OK;
}
int32_t vg_iec_ese_print_info(VgIecEseAdapter *adapter){return adapter==NULL?2:0;}
static int append_call(uint8_t *response,uint64_t *cursor,uint64_t limit,uint8_t operation,const char *error,const EseInstance *instance){uint8_t prefix[4]={operation,0,0,0};int32_t code=call_ok(error)?0:2;const char *message=call_ok(error)?instance->abi->last_error:error;APPEND(response,*cursor,limit,prefix,4);APPEND(response,*cursor,limit,&code,4);APPEND_TEXT(response,*cursor,limit,message);APPEND_TEXT(response,*cursor,limit,instance->abi->last_general);return VG_NATIVE_OK;}
static int append_termination_call(uint8_t *response,uint64_t *cursor,uint64_t limit,const char *error){uint8_t prefix[4]={VG_NATIVE_TERMINATE,0,0,0};int32_t code=call_ok(error)?0:2;APPEND(response,*cursor,limit,prefix,4);APPEND(response,*cursor,limit,&code,4);APPEND_TEXT(response,*cursor,limit,error);APPEND_TEXT(response,*cursor,limit,"");return VG_NATIVE_OK;}
static int append_outputs(uint8_t *response,uint64_t *cursor,uint64_t limit,const EseInstance *instance){uint32_t index;uint8_t tag=9;if(instance->output_count>0&&instance->abi->outputs==NULL)return VG_NATIVE_ABI_FAILURE;APPEND_U32(response,*cursor,limit,instance->output_count);for(index=0;index<instance->output_count;++index){if(!isfinite(instance->abi->outputs[index]))return VG_NATIVE_ABI_FAILURE;APPEND(response,*cursor,limit,&tag,1);APPEND(response,*cursor,limit,&instance->abi->outputs[index],8);}return VG_NATIVE_OK;}
static int parse_instance(VgIecEseAdapter *adapter,const uint8_t **payload,uint64_t *remaining,EseInstance **created){
 const uint8_t *cursor=*payload;uint32_t id_size,input_count,index,override_count;uint8_t mode;char *identifier;EseInstance *instance;
 READ_U32(cursor,*remaining,id_size);REQUIRE(*remaining,id_size);if(id_size==0||id_size>=4096U||memchr(cursor,0,id_size)!=NULL)return VG_NATIVE_BAD_PAYLOAD;identifier=(char*)malloc((size_t)id_size+1U);if(identifier==NULL)return VG_NATIVE_ABI_FAILURE;memcpy(identifier,cursor,id_size);identifier[id_size]=0;cursor+=id_size;*remaining-=id_size;REQUIRE(*remaining,4);mode=cursor[0];if((mode!=1&&mode!=2)||cursor[1]!=0||cursor[2]!=0||cursor[3]!=0||(adapter->info->mode!=mode&&adapter->info->mode!=3)){free(identifier);return VG_NATIVE_BAD_PAYLOAD;}cursor+=4;*remaining-=4;
 instance=(EseInstance*)calloc(1,sizeof(EseInstance));if(instance==NULL){free(identifier);return VG_NATIVE_ABI_FAILURE;}instance->identifier=identifier;if(!flat_count(adapter,1,&instance->input_count)||!flat_count(adapter,0,&instance->output_count)){destroy_instance(instance);return VG_NATIVE_ABI_FAILURE;}instance->abi=adapter->create(1U,adapter->info->sample_time);if(instance->abi==NULL){destroy_instance(instance);return VG_NATIVE_ABI_FAILURE;}if((instance->input_count>0&&instance->abi->inputs==NULL)||(instance->output_count>0&&instance->abi->outputs==NULL)||(adapter->info->parameter_count>0&&instance->abi->parameters==NULL)){destroy_instance(instance);return VG_NATIVE_ABI_FAILURE;}
 READ_U32(cursor,*remaining,input_count);if(input_count!=instance->input_count){destroy_instance(instance);return VG_NATIVE_BAD_PAYLOAD;}for(index=0;index<input_count;++index){REQUIRE(*remaining,9);if(cursor[0]!=9){destroy_instance(instance);return VG_NATIVE_BAD_PAYLOAD;}memcpy(&instance->abi->inputs[index],cursor+1,8);if(!isfinite(instance->abi->inputs[index])){destroy_instance(instance);return VG_NATIVE_BAD_PAYLOAD;}cursor+=9;*remaining-=9;}for(index=0;index<(uint32_t)adapter->info->parameter_count;++index)instance->abi->parameters[index]=adapter->info->parameters[index].default_value;
 READ_U32(cursor,*remaining,override_count);if(override_count>(uint32_t)adapter->info->parameter_count){destroy_instance(instance);return VG_NATIVE_BAD_PAYLOAD;}for(index=0;index<override_count;++index){uint32_t ordinal;READ_U32(cursor,*remaining,ordinal);REQUIRE(*remaining,13);if(ordinal>=(uint32_t)adapter->info->parameter_count||cursor[0]!=9||cursor[1]!=0||cursor[2]!=0||cursor[3]!=0||cursor[4]!=9){destroy_instance(instance);return VG_NATIVE_BAD_PAYLOAD;}memcpy(&instance->abi->parameters[ordinal],cursor+5,8);if(!isfinite(instance->abi->parameters[ordinal])){destroy_instance(instance);return VG_NATIVE_BAD_PAYLOAD;}cursor+=13;*remaining-=13;}*payload=cursor;*created=instance;return VG_NATIVE_OK;
}
int vg_iec_ese_initialize(VgIecEseAdapter *adapter,const uint8_t *payload,uint64_t payload_size,uint8_t **response,uint64_t *response_size){const uint8_t *cursor=payload;uint64_t remaining=payload_size,out_cursor=0;uint32_t count,index;uint8_t *out;if(adapter==NULL)return VG_NATIVE_BAD_PAYLOAD;READ_U32(cursor,remaining,count);if(count==0||adapter->instance_count+count>adapter->limits.maximum_instances)return VG_NATIVE_BAD_PAYLOAD;out=(uint8_t*)malloc((size_t)adapter->limits.maximum_frame_bytes);if(out==NULL)return VG_NATIVE_ABI_FAILURE;APPEND_U32(out,out_cursor,adapter->limits.maximum_frame_bytes,count);for(index=0;index<count;++index){EseInstance *instance=NULL;const char *error;uint32_t id_size;int status=parse_instance(adapter,&cursor,&remaining,&instance);if(status!=VG_NATIVE_OK){free(out);return status;}if(adapter->instance_count>0&&strcmp(adapter->instances[adapter->instance_count-1]->identifier,instance->identifier)>=0){destroy_instance(instance);free(out);return VG_NATIVE_BAD_PAYLOAD;}adapter->instances[adapter->instance_count++]=instance;id_size=(uint32_t)strlen(instance->identifier);APPEND_U32(out,out_cursor,adapter->limits.maximum_frame_bytes,id_size);APPEND(out,out_cursor,adapter->limits.maximum_frame_bytes,instance->identifier,id_size);APPEND_U32(out,out_cursor,adapter->limits.maximum_frame_bytes,3);error=adapter->check_parameters(instance->abi);status=append_call(out,&out_cursor,adapter->limits.maximum_frame_bytes,VG_NATIVE_CHECK_PARAMETERS,error,instance);if(status==VG_NATIVE_OK&&call_ok(error)){error=adapter->initialize(instance->abi);status=append_call(out,&out_cursor,adapter->limits.maximum_frame_bytes,VG_NATIVE_INITIALIZE_CALL,error,instance);}if(status==VG_NATIVE_OK&&call_ok(error)){error=adapter->outputs(instance->abi,1U);status=append_call(out,&out_cursor,adapter->limits.maximum_frame_bytes,VG_NATIVE_OUTPUTS,error,instance);}if(status!=VG_NATIVE_OK||!call_ok(error)){free(out);return VG_NATIVE_ABI_FAILURE;}instance->started=1;status=append_outputs(out,&out_cursor,adapter->limits.maximum_frame_bytes,instance);if(status!=VG_NATIVE_OK){free(out);return status;}}if(remaining!=0){free(out);return VG_NATIVE_BAD_PAYLOAD;}*response=out;*response_size=out_cursor;return VG_NATIVE_OK;}int vg_iec_ese_sample(VgIecEseAdapter *adapter,const uint8_t *payload,uint64_t payload_size,uint8_t **response,uint64_t *response_size){const uint8_t *cursor=payload;uint64_t remaining=payload_size,out_cursor=0;double time;uint32_t count,row;uint8_t *out;char previous[4096]={0};if(adapter==NULL)return VG_NATIVE_BAD_PAYLOAD;REQUIRE(remaining,8);memcpy(&time,cursor,8);cursor+=8;remaining-=8;if(!isfinite(time)||time<=0.0)return VG_NATIVE_BAD_PAYLOAD;READ_U32(cursor,remaining,count);if(count==0||count>adapter->instance_count)return VG_NATIVE_BAD_PAYLOAD;out=(uint8_t*)malloc((size_t)adapter->limits.maximum_frame_bytes);if(out==NULL)return VG_NATIVE_ABI_FAILURE;APPEND_U32(out,out_cursor,adapter->limits.maximum_frame_bytes,count);for(row=0;row<count;++row){uint32_t id_size,instance_index,input_count,index;char identifier[4096];EseInstance *instance=NULL;const char *error;int status;READ_U32(cursor,remaining,id_size);REQUIRE(remaining,id_size);if(id_size==0||id_size>=sizeof(identifier)||memchr(cursor,0,id_size)!=NULL){free(out);return VG_NATIVE_BAD_PAYLOAD;}memcpy(identifier,cursor,id_size);identifier[id_size]=0;cursor+=id_size;remaining-=id_size;if(strcmp(previous,identifier)>=0){free(out);return VG_NATIVE_BAD_PAYLOAD;}memcpy(previous,identifier,id_size+1U);for(instance_index=0;instance_index<adapter->instance_count;++instance_index)if(strcmp(adapter->instances[instance_index]->identifier,identifier)==0){instance=adapter->instances[instance_index];break;}if(instance==NULL||!instance->started||instance->terminated){free(out);return VG_NATIVE_BAD_PAYLOAD;}READ_U32(cursor,remaining,input_count);if(input_count!=instance->input_count){free(out);return VG_NATIVE_BAD_PAYLOAD;}for(index=0;index<input_count;++index){REQUIRE(remaining,9);if(cursor[0]!=9){free(out);return VG_NATIVE_BAD_PAYLOAD;}memcpy(&instance->abi->inputs[index],cursor+1,8);if(!isfinite(instance->abi->inputs[index])){free(out);return VG_NATIVE_BAD_PAYLOAD;}cursor+=9;remaining-=9;}error=adapter->update(instance->abi);if(call_ok(error))error=adapter->outputs(instance->abi,1U);APPEND_U32(out,out_cursor,adapter->limits.maximum_frame_bytes,id_size);APPEND(out,out_cursor,adapter->limits.maximum_frame_bytes,identifier,id_size);APPEND_U32(out,out_cursor,adapter->limits.maximum_frame_bytes,1);status=append_call(out,&out_cursor,adapter->limits.maximum_frame_bytes,VG_NATIVE_OUTPUTS,error,instance);if(status==VG_NATIVE_OK)status=append_outputs(out,&out_cursor,adapter->limits.maximum_frame_bytes,instance);if(status!=VG_NATIVE_OK||!call_ok(error)){free(out);return VG_NATIVE_ABI_FAILURE;}}if(remaining!=0){free(out);return VG_NATIVE_BAD_PAYLOAD;}*response=out;*response_size=out_cursor;return VG_NATIVE_OK;}
int vg_iec_ese_close(VgIecEseAdapter *adapter,const uint8_t *payload,uint64_t payload_size,uint8_t **response,uint64_t *response_size){uint8_t *out;uint64_t cursor=0;uint32_t count=0,index;(void)payload;if(adapter==NULL||payload_size!=0)return VG_NATIVE_BAD_PAYLOAD;out=(uint8_t*)malloc((size_t)adapter->limits.maximum_frame_bytes);if(out==NULL)return VG_NATIVE_ABI_FAILURE;for(index=0;index<adapter->instance_count;++index)if(adapter->instances[index]->started&&!adapter->instances[index]->terminated)count+=1;APPEND_U32(out,cursor,adapter->limits.maximum_frame_bytes,count);for(index=0;index<adapter->instance_count;++index){EseInstance *instance=adapter->instances[index];if(instance->started&&!instance->terminated){uint32_t id_size=(uint32_t)strlen(instance->identifier);const char *error=adapter->terminate(instance->abi);int status;APPEND_U32(out,cursor,adapter->limits.maximum_frame_bytes,id_size);APPEND(out,cursor,adapter->limits.maximum_frame_bytes,instance->identifier,id_size);status=append_termination_call(out,&cursor,adapter->limits.maximum_frame_bytes,error);if(status!=VG_NATIVE_OK){free(out);return status;}instance->terminated=1;}}*response=out;*response_size=cursor;return VG_NATIVE_OK;}
void vg_iec_ese_destroy(VgIecEseAdapter *adapter) {
    uint32_t index;
    if (adapter == NULL) {
        return;
    } else {
        index = 0;
    }
    while (index < adapter->instance_count) {
        EseInstance *instance = adapter->instances[index];
        if (instance != NULL && instance->started && !instance->terminated
                && adapter->terminate != NULL) {
            adapter->terminate(instance->abi);
            instance->terminated = 1;
        } else {
            /* Unstarted, terminated, or incomplete instances need only local cleanup. */
        }
        destroy_instance(instance);
        index += 1;
    }
    free(adapter->instances);
    vg_iec_ese_initialize_adapter(adapter);
}