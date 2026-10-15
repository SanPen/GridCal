/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 * SPDX-License-Identifier: MPL-2.0
 */
#include <math.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include "adapter_ieee_cigre_v1_0.h"
#include "protocol.h"
#include "platform.h"

#define REQUIRE(R,N) do { if ((uint64_t)(R) < (uint64_t)(N)) return VG_NATIVE_BAD_PAYLOAD; } while (0)
#define READ_U32(P,R,V) do { REQUIRE((R),4); memcpy(&(V),(P),4); (P)+=4; (R)-=4; } while (0)
#define APPEND(B,C,L,S,N) do { if ((C)+(uint64_t)(N)>(L)) return VG_NATIVE_BAD_PAYLOAD; memcpy((B)+(C),(S),(size_t)(N)); (C)+=(uint64_t)(N); } while (0)
#define APPEND_U32(B,C,L,V) do { uint32_t value_=(uint32_t)(V); APPEND((B),(C),(L),&value_,4); } while (0)
#define APPEND_TEXT(B,C,L,T) do { const char *text_=(T)==NULL?"":(T); uint64_t size_=0; if(!vg_native_bounded_text_size(text_,16777216U,&size_))return VG_NATIVE_ABI_FAILURE; APPEND_U32((B),(C),(L),size_); APPEND((B),(C),(L),text_,size_); } while (0)

static int add_size(uint64_t left, uint64_t right, uint64_t *result) {
    if (result == NULL || UINT64_MAX - left < right) return 0;
    *result = left + right; return 1;
}

static int flattened_count(const VgIeeeCigreV10Adapter *adapter, int inputs, uint32_t *count) {
    int32_t index; int32_t port_count; uint64_t scalars = 0;
    if (adapter == NULL || adapter->info == NULL || count == NULL) return 0;
    port_count = inputs ? adapter->info->input_count : adapter->info->output_count;
    for (index=0; index<port_count; ++index) {
        int32_t width = inputs ? adapter->info->inputs[index].width : adapter->info->outputs[index].width;
        if (width<=0 || !add_size(scalars,(uint64_t)width,&scalars)
                || scalars>adapter->limits.maximum_scalar_slots || scalars>UINT32_MAX) return 0;
    }
    *count=(uint32_t)scalars; return 1;
}

void vg_ieee_cigre_v1_0_initialize_adapter(VgIeeeCigreV10Adapter *adapter) {
    if (adapter != NULL) {
        memset(adapter, 0, sizeof(*adapter));
    } else {
        return;
    }
}

int vg_ieee_cigre_v1_0_bind(const VgPlatformLibrary *library,
                            const VgNativeAdapterLimits *limits,
                            VgIeeeCigreV10Adapter *adapter) {
    VgV10GetInfo get_info;
    if (library == NULL || limits == NULL || adapter == NULL) {
        return VG_NATIVE_BAD_PAYLOAD;
    } else {
        vg_ieee_cigre_v1_0_initialize_adapter(adapter);
    }
    get_info = (VgV10GetInfo)vg_platform_library_symbol(library, "Model_GetInfo");
    adapter->check_parameters = (VgV10Call)vg_platform_library_symbol(
        library, "Model_CheckParameters"
    );
    adapter->initialize = (VgV10Call)vg_platform_library_symbol(library, "Model_Initialize");
    adapter->outputs = (VgV10Outputs)vg_platform_library_symbol(library, "Model_Outputs");
    adapter->update = (VgV10Call)vg_platform_library_symbol(library, "Model_Update");
    adapter->terminate = (VgV10Call)vg_platform_library_symbol(library, "Model_Terminate");
    adapter->print_info = (VgV10PrintInfo)vg_platform_library_symbol(library, "Model_PrintInfo");
    if (get_info == NULL || adapter->check_parameters == NULL || adapter->initialize == NULL
            || adapter->outputs == NULL || adapter->update == NULL || adapter->terminate == NULL
            || adapter->print_info == NULL
            || vg_platform_library_symbol(library, "Model_Loadflow") == NULL
            || vg_platform_library_symbol(library, "Model_Derivatives") == NULL) {
        vg_ieee_cigre_v1_0_destroy(adapter);
        return VG_NATIVE_ABI_FAILURE;
    } else {
        adapter->limits = *limits;
        adapter->info = get_info();
        adapter->instances = (VgV10Instance **)calloc(
            limits->maximum_instances, sizeof(VgV10Instance *)
        );
    }
    if (adapter->info == NULL || adapter->instances == NULL) {
        vg_ieee_cigre_v1_0_destroy(adapter);
        return VG_NATIVE_ABI_FAILURE;
    } else {
        return VG_NATIVE_OK;
    }
}
int vg_ieee_cigre_v1_0_copy_model_info(VgIeeeCigreV10Adapter *adapter,
                                       uint8_t **payload,uint64_t *payload_size) {
    const VgV10ModelInfo *info; uint8_t *buffer; uint64_t cursor=0, scalars=0;
    int direction; int32_t index;
    if(adapter==NULL||payload==NULL||payload_size==NULL)return VG_NATIVE_BAD_PAYLOAD;
    info=adapter->info;
    if(memcmp(info->api_release,"\x01\x00\x00\x00",4)!=0||!isfinite(info->sample_time)
            ||info->sample_time<=0.0||info->model_mode<1||info->model_mode>3
            ||info->loadflow_flag>1||info->input_count<0||(uint32_t)info->input_count>adapter->limits.maximum_ports
            ||info->output_count<0||(uint32_t)info->output_count>adapter->limits.maximum_ports
            ||info->parameter_count<0||(uint32_t)info->parameter_count>adapter->limits.maximum_parameters
            ||info->continuous_state_count<0||info->miscellaneous_state_bytes<0
            ||info->int_state_count<0||info->float_state_count<0||info->double_state_count<0
            ||(uint64_t)info->continuous_state_count+(uint64_t)info->int_state_count
              +(uint64_t)info->float_state_count+(uint64_t)info->double_state_count
              >adapter->limits.maximum_state_scalars)return VG_NATIVE_ABI_FAILURE;
    buffer=(uint8_t*)malloc((size_t)adapter->limits.maximum_frame_bytes);
    if(buffer==NULL)return VG_NATIVE_ABI_FAILURE;
    {
        uint8_t interface_record[4]={2,0,0,0};
        uint8_t sample_record[4]={1,info->model_mode,info->loadflow_flag,0};
        APPEND(buffer,cursor,adapter->limits.maximum_frame_bytes,interface_record,4);
        APPEND(buffer,cursor,adapter->limits.maximum_frame_bytes,info->api_release,4);
        APPEND_TEXT(buffer,cursor,adapter->limits.maximum_frame_bytes,info->model_name);
        APPEND_TEXT(buffer,cursor,adapter->limits.maximum_frame_bytes,info->model_version);
        APPEND_TEXT(buffer,cursor,adapter->limits.maximum_frame_bytes,info->model_description);
        APPEND_TEXT(buffer,cursor,adapter->limits.maximum_frame_bytes,info->version_control_info);
        APPEND_TEXT(buffer,cursor,adapter->limits.maximum_frame_bytes,info->general_information);
        APPEND_TEXT(buffer,cursor,adapter->limits.maximum_frame_bytes,info->model_created);
        APPEND_TEXT(buffer,cursor,adapter->limits.maximum_frame_bytes,info->model_creator);
        APPEND_TEXT(buffer,cursor,adapter->limits.maximum_frame_bytes,info->model_last_modified_date);
        APPEND_TEXT(buffer,cursor,adapter->limits.maximum_frame_bytes,info->model_last_modified_by);
        APPEND_TEXT(buffer,cursor,adapter->limits.maximum_frame_bytes,info->model_modified_comment);
        APPEND_TEXT(buffer,cursor,adapter->limits.maximum_frame_bytes,info->model_modified_history);
        APPEND_TEXT(buffer,cursor,adapter->limits.maximum_frame_bytes,info->code_generated_on);
        APPEND_TEXT(buffer,cursor,adapter->limits.maximum_frame_bytes,info->included_solver);
        APPEND(buffer,cursor,adapter->limits.maximum_frame_bytes,&info->sample_time,8);
        APPEND(buffer,cursor,adapter->limits.maximum_frame_bytes,&info->sample_time,8);
        APPEND(buffer,cursor,adapter->limits.maximum_frame_bytes,sample_record,4);
    }
    for(direction=0;direction<2;++direction){
        int32_t count=direction==0?info->input_count:info->output_count;
        if(count>0&&((direction==0&&info->inputs==NULL)||(direction==1&&info->outputs==NULL))){free(buffer);return VG_NATIVE_ABI_FAILURE;}
        APPEND_U32(buffer,cursor,adapter->limits.maximum_frame_bytes,count);
        for(index=0;index<count;++index){
            const char *name=direction==0?info->inputs[index].name:info->outputs[index].name;
            const char *path=direction==0?info->inputs[index].block_path:info->outputs[index].block_path;
            const char *unit=direction==0?info->inputs[index].unit:info->outputs[index].unit;
            int32_t width=direction==0?info->inputs[index].width:info->outputs[index].width;
            int32_t semantic=direction==0?info->inputs[index].semantic:info->outputs[index].semantic;
            uint8_t real64_record[4]={9,0,0,0};
            if(width<=0||!add_size(scalars,(uint64_t)width,&scalars)||scalars>adapter->limits.maximum_scalar_slots){free(buffer);return VG_NATIVE_ABI_FAILURE;}
            APPEND_TEXT(buffer,cursor,adapter->limits.maximum_frame_bytes,name);
            APPEND_TEXT(buffer,cursor,adapter->limits.maximum_frame_bytes,"");
            APPEND_TEXT(buffer,cursor,adapter->limits.maximum_frame_bytes,unit);
            APPEND_TEXT(buffer,cursor,adapter->limits.maximum_frame_bytes,path);
            APPEND(buffer,cursor,adapter->limits.maximum_frame_bytes,real64_record,4);
            APPEND_U32(buffer,cursor,adapter->limits.maximum_frame_bytes,width);
            APPEND_U32(buffer,cursor,adapter->limits.maximum_frame_bytes,semantic);
        }
    }
    if(info->parameter_count>0&&info->parameters==NULL){free(buffer);return VG_NATIVE_ABI_FAILURE;}
    APPEND_U32(buffer,cursor,adapter->limits.maximum_frame_bytes,info->parameter_count);
    for(index=0;index<info->parameter_count;++index){
        const VgV10Parameter *parameter=&info->parameters[index]; uint8_t record[4]={9,0,0,0};
        uint8_t bounds[4]={1,1,0,0}; uint8_t tag=9;
        if((parameter->fixed_value!=0&&parameter->fixed_value!=1)||!isfinite(parameter->default_value)
                ||!isfinite(parameter->minimum_value)||!isfinite(parameter->maximum_value)){free(buffer);return VG_NATIVE_ABI_FAILURE;}
        record[1]=(uint8_t)parameter->fixed_value;
        APPEND_TEXT(buffer,cursor,adapter->limits.maximum_frame_bytes,parameter->name);
        APPEND_TEXT(buffer,cursor,adapter->limits.maximum_frame_bytes,"");
        APPEND_TEXT(buffer,cursor,adapter->limits.maximum_frame_bytes,parameter->description);
        APPEND_TEXT(buffer,cursor,adapter->limits.maximum_frame_bytes,parameter->unit);
        APPEND(buffer,cursor,adapter->limits.maximum_frame_bytes,record,4);
        APPEND(buffer,cursor,adapter->limits.maximum_frame_bytes,&tag,1);
        APPEND(buffer,cursor,adapter->limits.maximum_frame_bytes,&parameter->default_value,8);
        APPEND(buffer,cursor,adapter->limits.maximum_frame_bytes,bounds,4);
        APPEND(buffer,cursor,adapter->limits.maximum_frame_bytes,&tag,1);
        APPEND(buffer,cursor,adapter->limits.maximum_frame_bytes,&parameter->minimum_value,8);
        APPEND(buffer,cursor,adapter->limits.maximum_frame_bytes,&tag,1);
        APPEND(buffer,cursor,adapter->limits.maximum_frame_bytes,&parameter->maximum_value,8);
    }
    APPEND_U32(buffer,cursor,adapter->limits.maximum_frame_bytes,info->continuous_state_count);
    APPEND_U32(buffer,cursor,adapter->limits.maximum_frame_bytes,info->miscellaneous_state_bytes);
    APPEND_U32(buffer,cursor,adapter->limits.maximum_frame_bytes,info->int_state_count);
    APPEND_U32(buffer,cursor,adapter->limits.maximum_frame_bytes,info->float_state_count);
    APPEND_U32(buffer,cursor,adapter->limits.maximum_frame_bytes,info->double_state_count);
    *payload=buffer;*payload_size=cursor;return VG_NATIVE_OK;
}

int32_t vg_ieee_cigre_v1_0_print_info(VgIeeeCigreV10Adapter *adapter){
    if(adapter==NULL||adapter->print_info==NULL)return 2;
    return adapter->print_info()==NULL?0:2;
}
static void destroy_instance(VgV10Instance *instance){
    if(instance==NULL)return;
    free(instance->identifier);free(instance->inputs);free(instance->outputs);free(instance->parameters);
    free(instance->continuous_states);free(instance->state_derivatives);free(instance->miscellaneous_states);
    free(instance->int_states);free(instance->float_states);free(instance->double_states);free(instance);
}

static VgV10Instance *allocate_instance(VgIeeeCigreV10Adapter *adapter,char *identifier){
    const VgV10ModelInfo *info=adapter->info;VgV10Instance *instance;
    uint64_t required_bytes;
    instance=(VgV10Instance*)calloc(1,sizeof(VgV10Instance));
    if(instance==NULL)return NULL;
    instance->identifier=identifier;
    if(!flattened_count(adapter,1,&instance->input_count)||!flattened_count(adapter,0,&instance->output_count)){
        destroy_instance(instance);return NULL;
    }
    required_bytes=((uint64_t)instance->input_count+(uint64_t)instance->output_count
        +(uint64_t)info->parameter_count+((uint64_t)info->continuous_state_count*2U)
        +(uint64_t)info->int_state_count+(uint64_t)info->float_state_count
        +(uint64_t)info->double_state_count)*8U+(uint64_t)info->miscellaneous_state_bytes;
    if(required_bytes>adapter->limits.maximum_instance_bytes){destroy_instance(instance);return NULL;}
    instance->inputs=(double*)calloc(instance->input_count==0?1U:instance->input_count,sizeof(double));
    instance->outputs=(double*)calloc(instance->output_count==0?1U:instance->output_count,sizeof(double));
    instance->parameters=(double*)calloc(info->parameter_count==0?1U:(uint32_t)info->parameter_count,sizeof(double));
    instance->continuous_states=(double*)calloc(info->continuous_state_count==0?1U:(uint32_t)info->continuous_state_count,sizeof(double));
    instance->state_derivatives=(double*)calloc(info->continuous_state_count==0?1U:(uint32_t)info->continuous_state_count,sizeof(double));
    instance->miscellaneous_states=(uint8_t*)calloc(info->miscellaneous_state_bytes==0?1U:(uint32_t)info->miscellaneous_state_bytes,1U);
    instance->int_states=(int32_t*)calloc(info->int_state_count==0?1U:(uint32_t)info->int_state_count,sizeof(int32_t));
    instance->float_states=(float*)calloc(info->float_state_count==0?1U:(uint32_t)info->float_state_count,sizeof(float));
    instance->double_states=(double*)calloc(info->double_state_count==0?1U:(uint32_t)info->double_state_count,sizeof(double));
    if(instance->inputs==NULL||instance->outputs==NULL||instance->parameters==NULL
            ||instance->continuous_states==NULL||instance->state_derivatives==NULL
            ||instance->miscellaneous_states==NULL||instance->int_states==NULL
            ||instance->float_states==NULL||instance->double_states==NULL){destroy_instance(instance);return NULL;}
    instance->abi.inputs=instance->inputs;instance->abi.outputs=instance->outputs;
    instance->abi.parameters=instance->parameters;instance->abi.continuous_states=instance->continuous_states;
    instance->abi.state_derivatives=instance->state_derivatives;
    instance->abi.miscellaneous_states=instance->miscellaneous_states;
    instance->abi.int_states=instance->int_states;instance->abi.float_states=instance->float_states;
    instance->abi.double_states=instance->double_states;return instance;
}

static int call_succeeded(const char *returned_error){return returned_error==NULL||returned_error[0]==0;}

static int append_call(uint8_t *response,uint64_t *cursor,uint64_t limit,uint8_t operation,
                       const char *returned_error,const VgV10Instance *instance){
    uint8_t prefix[4]={operation,0,0,0};int32_t return_code=call_succeeded(returned_error)?0:2;
    const char *error_message=call_succeeded(returned_error)?instance->abi.last_error_message:returned_error;
    APPEND(response,*cursor,limit,prefix,4);APPEND(response,*cursor,limit,&return_code,4);
    APPEND_TEXT(response,*cursor,limit,error_message);
    APPEND_TEXT(response,*cursor,limit,instance->abi.last_general_message);return VG_NATIVE_OK;
}

static int append_outputs(uint8_t *response,uint64_t *cursor,uint64_t limit,const VgV10Instance *instance){
    uint32_t index;uint8_t tag=9;APPEND_U32(response,*cursor,limit,instance->output_count);
    for(index=0;index<instance->output_count;++index){
        if(!isfinite(instance->outputs[index]))return VG_NATIVE_ABI_FAILURE;
        APPEND(response,*cursor,limit,&tag,1);APPEND(response,*cursor,limit,&instance->outputs[index],8);
    }
    return VG_NATIVE_OK;
}

static int parse_instance(VgIeeeCigreV10Adapter *adapter,const uint8_t **payload,
                          uint64_t *remaining,VgV10Instance **created){
    const uint8_t *cursor=*payload;uint32_t identifier_size,input_count,input_index,override_count,override_index;
    uint8_t mode;char *identifier;VgV10Instance *instance;
    READ_U32(cursor,*remaining,identifier_size);REQUIRE(*remaining,identifier_size);
    if(identifier_size==0||identifier_size>=4096U||memchr(cursor,0,identifier_size)!=NULL)return VG_NATIVE_BAD_PAYLOAD;
    identifier=(char*)malloc((size_t)identifier_size+1U);if(identifier==NULL)return VG_NATIVE_ABI_FAILURE;
    memcpy(identifier,cursor,identifier_size);identifier[identifier_size]=0;cursor+=identifier_size;*remaining-=identifier_size;
    REQUIRE(*remaining,4);mode=cursor[0];
    if((mode!=1&&mode!=2)||cursor[1]!=0||cursor[2]!=0||cursor[3]!=0
            ||(adapter->info->model_mode!=mode&&adapter->info->model_mode!=3)){free(identifier);return VG_NATIVE_BAD_PAYLOAD;}
    cursor+=4;*remaining-=4;instance=allocate_instance(adapter,identifier);
    if(instance==NULL)return VG_NATIVE_ABI_FAILURE;
    READ_U32(cursor,*remaining,input_count);if(input_count!=instance->input_count){destroy_instance(instance);return VG_NATIVE_BAD_PAYLOAD;}
    for(input_index=0;input_index<input_count;++input_index){
        REQUIRE(*remaining,9);if(cursor[0]!=9){destroy_instance(instance);return VG_NATIVE_BAD_PAYLOAD;}
        memcpy(&instance->inputs[input_index],cursor+1,8);
        if(!isfinite(instance->inputs[input_index])){destroy_instance(instance);return VG_NATIVE_BAD_PAYLOAD;}
        cursor+=9;*remaining-=9;
    }
    for(override_index=0;override_index<(uint32_t)adapter->info->parameter_count;++override_index)
        instance->parameters[override_index]=adapter->info->parameters[override_index].default_value;
    READ_U32(cursor,*remaining,override_count);
    if(override_count>(uint32_t)adapter->info->parameter_count){destroy_instance(instance);return VG_NATIVE_BAD_PAYLOAD;}
    for(override_index=0;override_index<override_count;++override_index){
        uint32_t ordinal;READ_U32(cursor,*remaining,ordinal);REQUIRE(*remaining,13);
        if(ordinal>=(uint32_t)adapter->info->parameter_count||cursor[0]!=9
                ||cursor[1]!=(uint8_t)adapter->info->parameters[ordinal].fixed_value
                ||cursor[2]!=0||cursor[3]!=0||cursor[4]!=9){destroy_instance(instance);return VG_NATIVE_BAD_PAYLOAD;}
        memcpy(&instance->parameters[ordinal],cursor+5,8);
        if(!isfinite(instance->parameters[ordinal])){destroy_instance(instance);return VG_NATIVE_BAD_PAYLOAD;}
        cursor+=13;*remaining-=13;
    }
    *payload=cursor;*created=instance;return VG_NATIVE_OK;
}

int vg_ieee_cigre_v1_0_initialize(VgIeeeCigreV10Adapter *adapter,const uint8_t *payload,
                                  uint64_t payload_size,uint8_t **response,uint64_t *response_size){
    const uint8_t *cursor=payload;uint64_t remaining=payload_size;uint32_t count,index;
    uint8_t *output;uint64_t output_cursor=0;
    if(adapter==NULL||response==NULL||response_size==NULL)return VG_NATIVE_BAD_PAYLOAD;
    READ_U32(cursor,remaining,count);
    if(count==0||count>adapter->limits.maximum_instances||adapter->instance_count+count>adapter->limits.maximum_instances)return VG_NATIVE_BAD_PAYLOAD;
    output=(uint8_t*)malloc((size_t)adapter->limits.maximum_frame_bytes);if(output==NULL)return VG_NATIVE_ABI_FAILURE;
    APPEND_U32(output,output_cursor,adapter->limits.maximum_frame_bytes,count);
    for(index=0;index<count;++index){
        VgV10Instance *instance=NULL;int status=parse_instance(adapter,&cursor,&remaining,&instance);
        uint32_t identifier_size;const char *call_error;
        if(status!=VG_NATIVE_OK){free(output);return status;}
        if(adapter->instance_count>0&&strcmp(adapter->instances[adapter->instance_count-1]->identifier,instance->identifier)>=0){destroy_instance(instance);free(output);return VG_NATIVE_BAD_PAYLOAD;}
        adapter->instances[adapter->instance_count++]=instance;identifier_size=(uint32_t)strlen(instance->identifier);
        APPEND_U32(output,output_cursor,adapter->limits.maximum_frame_bytes,identifier_size);
        APPEND(output,output_cursor,adapter->limits.maximum_frame_bytes,instance->identifier,identifier_size);
        APPEND_U32(output,output_cursor,adapter->limits.maximum_frame_bytes,3);
        call_error=adapter->check_parameters(&instance->abi);
        status=append_call(output,&output_cursor,adapter->limits.maximum_frame_bytes,VG_NATIVE_CHECK_PARAMETERS,call_error,instance);
        if(status==VG_NATIVE_OK&&call_succeeded(call_error)){call_error=adapter->initialize(&instance->abi);status=append_call(output,&output_cursor,adapter->limits.maximum_frame_bytes,VG_NATIVE_INITIALIZE_CALL,call_error,instance);}
        if(status==VG_NATIVE_OK&&call_succeeded(call_error)){call_error=adapter->outputs(&instance->abi,1U);status=append_call(output,&output_cursor,adapter->limits.maximum_frame_bytes,VG_NATIVE_OUTPUTS,call_error,instance);}
        if(status!=VG_NATIVE_OK||!call_succeeded(call_error)){free(output);return status==VG_NATIVE_OK?VG_NATIVE_ABI_FAILURE:status;}
        instance->started=1;status=append_outputs(output,&output_cursor,adapter->limits.maximum_frame_bytes,instance);
        if(status!=VG_NATIVE_OK){free(output);return status;}
    }
    if(remaining!=0){free(output);return VG_NATIVE_BAD_PAYLOAD;}
    *response=output;*response_size=output_cursor;return VG_NATIVE_OK;
}
int vg_ieee_cigre_v1_0_sample(VgIeeeCigreV10Adapter *adapter,const uint8_t *payload,
                              uint64_t payload_size,uint8_t **response,uint64_t *response_size){
    const uint8_t *cursor=payload;uint64_t remaining=payload_size;double sample_time;
    uint32_t count,row_index;uint8_t *output;uint64_t output_cursor=0;char previous[4096]={0};
    if(adapter==NULL||response==NULL||response_size==NULL)return VG_NATIVE_BAD_PAYLOAD;
    REQUIRE(remaining,8);memcpy(&sample_time,cursor,8);cursor+=8;remaining-=8;
    if(!isfinite(sample_time)||sample_time<=0.0)return VG_NATIVE_BAD_PAYLOAD;
    READ_U32(cursor,remaining,count);if(count==0||count>adapter->instance_count)return VG_NATIVE_BAD_PAYLOAD;
    output=(uint8_t*)malloc((size_t)adapter->limits.maximum_frame_bytes);if(output==NULL)return VG_NATIVE_ABI_FAILURE;
    APPEND_U32(output,output_cursor,adapter->limits.maximum_frame_bytes,count);
    for(row_index=0;row_index<count;++row_index){
        uint32_t identifier_size,instance_index,input_count,input_index;char identifier[4096];
        VgV10Instance *instance=NULL;const char *call_error;int status;
        READ_U32(cursor,remaining,identifier_size);REQUIRE(remaining,identifier_size);
        if(identifier_size==0||identifier_size>=sizeof(identifier)||memchr(cursor,0,identifier_size)!=NULL){free(output);return VG_NATIVE_BAD_PAYLOAD;}
        memcpy(identifier,cursor,identifier_size);identifier[identifier_size]=0;cursor+=identifier_size;remaining-=identifier_size;
        if(strcmp(previous,identifier)>=0){free(output);return VG_NATIVE_BAD_PAYLOAD;}
        memcpy(previous,identifier,identifier_size+1U);
        for(instance_index=0;instance_index<adapter->instance_count;++instance_index){
            if(strcmp(adapter->instances[instance_index]->identifier,identifier)==0){instance=adapter->instances[instance_index];break;}
        }
        if(instance==NULL||!instance->started||instance->terminated){free(output);return VG_NATIVE_BAD_PAYLOAD;}
        READ_U32(cursor,remaining,input_count);if(input_count!=instance->input_count){free(output);return VG_NATIVE_BAD_PAYLOAD;}
        for(input_index=0;input_index<input_count;++input_index){
            REQUIRE(remaining,9);if(cursor[0]!=9){free(output);return VG_NATIVE_BAD_PAYLOAD;}
            memcpy(&instance->inputs[input_index],cursor+1,8);
            if(!isfinite(instance->inputs[input_index])){free(output);return VG_NATIVE_BAD_PAYLOAD;}
            cursor+=9;remaining-=9;
        }
        call_error=adapter->update(&instance->abi);if(call_succeeded(call_error))call_error=adapter->outputs(&instance->abi,1U);
        APPEND_U32(output,output_cursor,adapter->limits.maximum_frame_bytes,identifier_size);
        APPEND(output,output_cursor,adapter->limits.maximum_frame_bytes,identifier,identifier_size);
        APPEND_U32(output,output_cursor,adapter->limits.maximum_frame_bytes,1);
        status=append_call(output,&output_cursor,adapter->limits.maximum_frame_bytes,VG_NATIVE_OUTPUTS,call_error,instance);
        if(status==VG_NATIVE_OK)status=append_outputs(output,&output_cursor,adapter->limits.maximum_frame_bytes,instance);
        if(status!=VG_NATIVE_OK||!call_succeeded(call_error)){free(output);return status==VG_NATIVE_OK?VG_NATIVE_ABI_FAILURE:status;}
    }
    if(remaining!=0){free(output);return VG_NATIVE_BAD_PAYLOAD;}
    *response=output;*response_size=output_cursor;return VG_NATIVE_OK;
}

int vg_ieee_cigre_v1_0_close(VgIeeeCigreV10Adapter *adapter,const uint8_t *payload,
                             uint64_t payload_size,uint8_t **response,uint64_t *response_size){
    uint8_t *output;uint64_t cursor=0;uint32_t count=0,index;(void)payload;
    if(adapter==NULL||payload_size!=0||response==NULL||response_size==NULL)return VG_NATIVE_BAD_PAYLOAD;
    output=(uint8_t*)malloc((size_t)adapter->limits.maximum_frame_bytes);if(output==NULL)return VG_NATIVE_ABI_FAILURE;
    for(index=0;index<adapter->instance_count;++index)if(adapter->instances[index]->started&&!adapter->instances[index]->terminated)count+=1;
    APPEND_U32(output,cursor,adapter->limits.maximum_frame_bytes,count);
    for(index=0;index<adapter->instance_count;++index){
        VgV10Instance *instance=adapter->instances[index];
        if(instance->started&&!instance->terminated){
            uint32_t identifier_size=(uint32_t)strlen(instance->identifier);const char *call_error=adapter->terminate(&instance->abi);
            int status;APPEND_U32(output,cursor,adapter->limits.maximum_frame_bytes,identifier_size);
            APPEND(output,cursor,adapter->limits.maximum_frame_bytes,instance->identifier,identifier_size);
            status=append_call(output,&cursor,adapter->limits.maximum_frame_bytes,VG_NATIVE_TERMINATE,call_error,instance);
            if(status!=VG_NATIVE_OK){free(output);return status;}instance->terminated=1;
        }
    }
    *response=output;*response_size=cursor;return VG_NATIVE_OK;
}

void vg_ieee_cigre_v1_0_destroy(VgIeeeCigreV10Adapter *adapter) {
    uint32_t index;
    if (adapter == NULL) {
        return;
    } else {
        index = 0;
    }
    while (index < adapter->instance_count) {
        VgV10Instance *instance = adapter->instances[index];
        if (instance != NULL && instance->started && !instance->terminated
                && adapter->terminate != NULL) {
            adapter->terminate(&instance->abi);
            instance->terminated = 1;
        } else {
            /* Unstarted, terminated, or incomplete instances need only local cleanup. */
        }
        destroy_instance(instance);
        index += 1;
    }
    free(adapter->instances);
    vg_ieee_cigre_v1_0_initialize_adapter(adapter);
}