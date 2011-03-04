"""
Base implementation of the "visitor pattern" as seen
"""

import inspect

class ClassA(object):
    def __init__(self):
        pass

class ClassB(object):
    def __init__(self):
        pass

methods = {}

class when(object):
    def __init__(self, argtype):
        self.argtype = argtype
    def __call__(self, func):
        print "assigning %s to func %s" % (self.argtype, func)
        self.func_name =func.__name__
        if not self.func_name in methods:
            methods[self.func_name] = method_overload(self.func_name)        
        methods[self.func_name].register(self.argtype, func)
        return methods[self.func_name]

# this is the actual overload information about a specific method name
class method_overload(object):
    def __init__(self, func_name):
        self.func_name = func_name
        self.registry = {}

    def register(self, argtype, func):
        self.registry[argtype] = func

    def __get__(self, obj, type=None):
        return method_caller(self, obj, type)

# this class is instantiated once per(!) method call with the object & the type
# that will be invoked
class method_caller(object):
    def __init__(self, overload, obj, type):
        self.overload = overload
        self.obj = obj
        self.type = type
        
    def __call__(self, *args, **kw):
        argtype = type(args[0])
        if not argtype in self.overload.registry:
            raise TypeError("Function %s has no overload registered for type %s" % 
                            (self.overload.func_name, argtype))
        func = self.overload.registry[argtype]
        func.__get__(self.obj, self.type)(*args, **kw)


class Sample:

    @when(int)
    def foo(self, a, b):
        print "int %s %d %d" % (self, a,b)

    @when(float)
    def foo(self,a, b, c):
        print "float %s %f %f %f" % (self, a,b,c)

    @when(str)
    def foo(self, a, b):
        print "str %s %s %s" % (self, a,b)


