#ifndef RUNTIME_FMI1_H
#define RUNTIME_FMI1_H

#include "generated_metadata.h"

#define MODEL_IDENTIFIER VG_MODEL_IDENTIFIER_TOKEN
#include "fmiModelFunctions.h"

#include "model_instance.h"

fmiStatus status_from_result(int result);

#endif
