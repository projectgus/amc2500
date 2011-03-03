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

registry = {}

class Visitor(object):
    def __init__(self, fun_name):
        self.fun_name = fun_name
        self.typemap = {}
    def __call__(self, *args, **kw):
        function = self.typemap.get(type(args[1]))
        if function is None:
            raise TypeError("no match")
        return function(*args, **kw)
    def register(self, argtype, function):
        if argtype in self.typemap:
            raise TypeError("duplicate registration")
        self.typemap[argtype] = function


def when(argtype):
    def register(function):   
        print function.__class__
        print dir(function)
        #print function.im_self
        print dir(function.func_code)
        print inspect.getargspec(function)
        name = function.__name__
        if not name in registry:
            mm = registry[name] = Visitor(name)        
        mm = registry.get(name)
        #inspect.getargspec(function)[0]
        mm.register(argtype, function)
        return mm
    return register


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


