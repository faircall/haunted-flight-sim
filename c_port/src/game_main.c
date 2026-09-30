/* Native executable hosting the complete C-compiled game modules.
 * Third-party packages still use the existing CPython runtime. */
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdio.h>
#include <direct.h>
#include "game_config.h"
int main(int argc,char **argv) {
    if(_chdir(HF_REPO_ROOT)) { perror("Game asset directory");return 1; }
    PyConfig config;PyConfig_InitPythonConfig(&config);
    PyStatus status=PyConfig_SetBytesString(&config,&config.home,HF_PYTHON_HOME);
    if(PyStatus_Exception(status))Py_ExitStatusException(status);
    config.parse_argv=0;
    status=PyConfig_SetBytesArgv(&config,argc,argv);
    if(PyStatus_Exception(status))Py_ExitStatusException(status);
    status=Py_InitializeFromConfig(&config);PyConfig_Clear(&config);
    if(PyStatus_Exception(status))Py_ExitStatusException(status);
    PyObject *paths=PySys_GetObject("path");
    PyObject *repo=PyUnicode_FromString(HF_REPO_ROOT),*runtime=PyUnicode_FromString(HF_RUNTIME_ROOT);
    PyList_Insert(paths,0,repo);PyList_Insert(paths,0,runtime);Py_DECREF(repo);Py_DECREF(runtime);
    PyObject *module=PyImport_ImportModule("native_entry"),*result=NULL;
    if(module)result=PyObject_CallMethod(module,"run",NULL);
    int exit_code=0;
    if(!result) { PyErr_Print();exit_code=1; }
    Py_XDECREF(result);Py_XDECREF(module);
    if(Py_FinalizeEx()<0)exit_code=120;
    return exit_code;
}
