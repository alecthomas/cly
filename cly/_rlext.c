/*
 *
 * Copyright (C) 2006-2007 Alec Thomas <alec@swapoff.org>
 *
 * This software is licensed as described in the file COPYING, which
 * you should have received as part of this distribution.
 *
 * vim: ts=4 sts=4 sw=4 et
 */
#include "Python.h"
#include <readline/readline.h>

static PyObject *
force_redisplay(PyObject *self, PyObject *noarg)
{
    rl_forced_update_display();
    Py_INCREF(Py_None);
    return Py_None;
}

PyDoc_STRVAR(doc_force_redisplay,
"force_redisplay() -> None\n\
Force the line to be updated and redisplayed, whether or not\n\
Readline thinks the screen display is correct.");

/* bind_key */
static struct {
    PyObject *callback;
    PyThreadState *tstate;
} bind_key_map[256];

static int
bind_key_handler(int count, int key)
{
    PyObject *args;
    PyObject *result;

    PyEval_RestoreThread(bind_key_map[key].tstate);
    args = Py_BuildValue((char*)"(ii)", count, key);
    result = PyEval_CallObject(bind_key_map[key].callback, args);
    if (result == NULL) {
        PyErr_Clear();
        Py_XDECREF(result);
    } else {
        Py_DECREF(result);
    }
    Py_DECREF(args);
    bind_key_map[key].tstate = PyEval_SaveThread();
    return 0;
}

static PyObject *
bind_key(PyObject *self, PyObject *args)
{
    int key;
    PyObject *result = NULL;
    PyObject *callback;

    if (PyArg_ParseTuple(args, (char*)"iO:bind_key", &key, &callback)) {
        if (!PyCallable_Check(callback)) {
            PyErr_SetString(PyExc_TypeError, "bind_key requires callable as second argument");
            return NULL;
        }
        if (key < 0 || key > 255) {
            PyErr_SetString(PyExc_TypeError, "bind_key requires key ordinal as first argument");
            return NULL;
        }
        bind_key_map[key].callback = callback;
        bind_key_map[key].tstate = PyThreadState_GET();
        rl_bind_key(key, bind_key_handler);
        Py_XINCREF(bind_key_map[key].callback);
        Py_INCREF(Py_None);
        result = Py_None;
    }
    return result;
}

PyDoc_STRVAR(doc_bind_key,
"bind_key(key, function) -> None\n\
Bind key to function. Function must be a callable with one argument \n\
representing the count for that key.");

static PyObject *
cursor(PyObject *self, PyObject *args)
{
    if (!PyArg_ParseTuple(args, (char*)"|i:set_cursor", &rl_point))
        return NULL;
    if (rl_point > rl_end)
        rl_point = rl_end;
    if (rl_point < 0)
        rl_point = 0;
    return PyInt_FromLong(rl_point);
}

PyDoc_STRVAR(doc_cursor,
"cursor([offset]) -> offset\n\
Set or get the cursor location.");

static struct PyMethodDef methods[] = {
    {(char*)"bind_key", bind_key, METH_VARARGS, doc_bind_key},
    {(char*)"force_redisplay", force_redisplay, METH_NOARGS, doc_force_redisplay},
    {(char*)"cursor", cursor, METH_VARARGS, doc_cursor},
    {NULL, NULL, 0, NULL},
};

PyMODINIT_FUNC
init_rlext(void)
{
    Py_InitModule((char*)"_rlext", methods);
}
