import copy

from intbase import InterpreterBase, ErrorType
from brewparse import parse_program
from element import Element

class Interpreter(InterpreterBase):
    def __init__(self, console_output=True, inp=None, trace_output=False):
        super().__init__(console_output, inp)

        self.funcs = {} # {(name,n_args):element,}
        self.vars = [] # [({name:val,},bool),]
        self.bops = {'+', '-', '*', '/', '==', '!=', '>', '>=', '<', '<=', '||', '&&'}

    def run(self, program):
        ast = parse_program(program)

        for func in ast.get('functions'):
            self.funcs[(func.get('name'),len(func.get('args')))] = func

        main_key = None

        for k in self.funcs:
            if k[0] == 'main':
                main_key = k
                break

        if main_key is None:
            super().error(ErrorType.NAME_ERROR, '')

        _, ret = self.run_fcall(self.funcs[main_key])
        if type(ret) == str: super().error(ErrorType.FAULT_ERROR, 'exception not caught')

    def run_vardef(self, statement):
        name = statement.get('name')

        if name in self.vars[-1][0] and name not in self.vars[-1][2]: # fix this
            super().error(ErrorType.NAME_ERROR, 'double')

        self.vars[-1][0][name] = None

    def run_assign(self, statement):
        name = statement.get('name')

        for scope_vars, is_func, _ in self.vars[::-1]:
            if name in scope_vars:
                # print("expression getting:", statement.get('expression'), name)
                # scope_vars[name] = statement.get('expression')
                res, ret = self.run_expr(statement.get('expression'), eager=False) # this shouldn't happen b/c of lazy nonevaluation
                # or you could change what run_expr returns (it could be an expression node or smth)
                # current idea: for run_assign, make a copy of the AST expression node and then replace all the variables
                # in the expression node with a copy of their values
                # then, when you eagerly evaluate, you have the proper "state" when x was assigned
                if type(ret) == str: return res, ret
                scope_vars[name] = res
                return None, None

            if is_func: break

        super().error(ErrorType.NAME_ERROR, '')

    def run_fcall(self, statement):
        fcall_name, args = statement.get('name'), statement.get('args')

        res, ret = None, None

        if fcall_name == 'inputi' or fcall_name == 'inputs':
            if len(args) > 1:
                super().error(ErrorType.NAME_ERROR, '')

            if args:
                res, ret = self.run_expr(args[0], eager=True) # SHOUDL THIS BE EAGER EVALUATION?
                # while type(res) == Element and type(ret) != str: res, ret = self.run_expr(res, eager=True)
                if type(ret) == str: return res, ret
                super().output(str(res))

            res = super().get_input()

            return (int(res), None) if fcall_name == 'inputi' else (res, None)

        if fcall_name == 'print':
            out = ''

            # print("QWER", self.vars)

            for arg in args:
                c_out, ret = self.run_expr(arg, eager=True)
                # while type(c_out) == Element and type(ret) != str: c_out, ret = self.run_expr(c_out, eager=True) 
                # c_out can also be a normal integer or string
                # c_out can be an element node if self.run_expr returns a node
                # while type(c_out) == Element:
                #     c_out, ret = self.run_expr(c_out, eager=True) # c_out can be a normal integer or an element node
                # print("COUT", c_out, ret, type(c_out))
                if type(ret) == str: return c_out, ret
                if type(c_out) == bool: out += str(c_out).lower()
                else: out += str(c_out)
            super().output(out)

            return None, None
        
        if (fcall_name, len(args)) not in self.funcs:
            super().error(ErrorType.NAME_ERROR, '')

        func_def = self.funcs[(fcall_name, len(args))]

        template_args = [a.get('name') for a in func_def.get('args')]
        passed_args = []
        for a in args:
            res, ret = self.run_expr(a, eager=False) # use lazy evaluation instead of eager evaluation
            if type(ret) == str: return res, ret
            passed_args.append(res)

        self.vars.append(({k:v for k,v in zip(template_args, passed_args)}, True, template_args))
        res, ret = self.run_statements(func_def.get('statements'))
        self.vars.pop()
        return res, ret

    def run_if(self, statement):
        cond, ret = self.run_expr(statement.get('condition'), eager=True) # should be eager evaluation
        # while type(cond) == Element and type(ret) != str: cond, ret = self.run_expr(cond, eager=True)
        if type(ret) == str: return cond, ret

        if type(cond) != bool:
            super().error(ErrorType.TYPE_ERROR, '')

        self.vars.append(({}, False, []))

        res, ret = None, False

        if cond:
            res, ret = self.run_statements(statement.get('statements'))
        elif statement.get('else_statements'):
            res, ret = self.run_statements(statement.get('else_statements'))

        self.vars.pop()

        return res, ret

    def run_for(self, statement):
        res, ret = None, False

        _, rai = self.run_assign(statement.get('init'))
        if type(rai) == str: return _, rai

        while True:
            for entry in self.vars:
                dictionary, status, _ = entry
                if 'x' in dictionary:
                    pass
                    # print("JJJs")
                    # print(dictionary['x'])  # Access and print the value of 'j'
            cond, rai = self.run_expr(statement.get('condition'), eager=True) # should be eager evaluation
            for entry in self.vars:
                dictionary, status, _ = entry
                if 'x' in dictionary: # x doesnt change now
                    pass
                    # print("???JJJ")
                    # print(dictionary['x'])  # Access and print the value of 'j'
            # while type(cond) == Element and type(ret) != str: cond, ret = self.run_expr(cond, eager=True)
            if type(rai) == str: return res, rai

            if type(cond) != bool:
                super().error(ErrorType.TYPE_ERROR, '')

            if ret == True or not cond: break

            self.vars.append(({}, False, []))
            res, ret = self.run_statements(statement.get('statements'))
            self.vars.pop()

            _, rai = self.run_assign(statement.get('update')) # should be lazy evaluation
            if type(rai) == str: return _, rai

        return res, ret
    
    def run_try(self, statement):
        res, ret = None, False
        self.vars.append(({}, False, []))
        res, ret = self.run_statements(statement.get('statements'))
        self.vars.pop()
        if type(ret) != str: return res, ret
        for catcher in statement.get('catchers'):
            if catcher.get('exception_type') == ret:
                self.vars.append(({}, False, []))
                res, ret = self.run_statements(catcher.get('statements'))
                self.vars.pop()
                break
        return res, ret

    def run_return(self, statement):
        expr = statement.get('expression')
        res, ret = self.run_expr(expr, eager=True) # fix this?
        # According to spec, the expressions in return statements are evaluated lazily.
        # eagerness should propogate
        if expr: return res, ret
        return None, True
    
    def run_raise(self, statement):
        expr = statement.get('exception_type')
        res, ret = self.run_expr(expr, eager=True) # should be eager evaluation
        # while type(res) == Element and type(ret) != str: res, ret = self.run_expr(res, eager=True)
        if type(ret) == str: return res, ret # case where exception_type is a raise
        if type(res) == str: return None, res # case where exception_type is a string
        super().error(ErrorType.TYPE_ERROR, '')
        

    def run_statements(self, statements):
        res, ret = None, False # do i need to add raise here?

        for statement in statements:
            kind = statement.elem_type

            if kind == 'vardef':
                self.run_vardef(statement)
            elif kind == '=':
                _, ret = self.run_assign(statement)
            elif kind == 'fcall':
                _, ret =  self.run_fcall(statement) # fcall can raise something
            elif kind == 'if':
                res, ret = self.run_if(statement) # if can raise something
            elif kind == 'for':
                res, ret = self.run_for(statement) # for can raise something
            elif kind == 'try':
                res, ret = self.run_try(statement)
            elif kind == 'return':
                res, rai = self.run_return(statement) # fix this?
                if type(rai) == str: return res, rai
                ret = True
            elif kind == 'raise':
                res, ret = self.run_raise(statement) # fix this?

            if ret == True or type(ret) == str: break


        return res, ret

    def run_expr(self, expr, eager):
        kind = expr.elem_type

        # put in a case for lazy nonevaluation of expressions and eager evaluation of expressions
        # eager evaluation can have multiple layers to it, causing a cascade of eager evaluations

        res, ret = None, None

        # if eager == False:
        #     print("EXPR", expr)
        #     # implement closures, replace all the variables in expr with their values
        #     new_expr = copy(expr)

        #     return new_expr, ret

        if kind == 'int' or kind == 'string' or kind == 'bool':
            if eager == False: return copy.deepcopy(expr), ret
            return expr.get('val'), ret # ret must be none

        elif kind == 'var':
            var_name = expr.get('name')

            for scope_vars, is_func, _ in self.vars[::-1]:
                if var_name in scope_vars:
                    if eager == False: return copy.deepcopy(scope_vars[var_name]), ret
                    res, ret = self.run_expr(scope_vars[var_name], eager=True) # res can be a normal number or an expression node
                    # while type(res) == Element and type(ret) != str: res, ret = self.run_expr(res, eager=True)
                    return res, ret
                    return scope_vars[var_name], ret # ret must be none

                if is_func: break

            if eager == False: return None, None

            super().error(ErrorType.NAME_ERROR, '')

        elif kind == 'fcall':
            if eager == False:
                new_expr = copy.deepcopy(expr)
                argList = new_expr.dict['args']
                for i in range(len(argList)):
                    # what is argList[i] doesn't exist???
                    argList[i] = self.run_expr(argList[i], eager=False)[0] # we can do res, ret but ret should always be None right?
                return new_expr, ret
            return self.run_fcall(expr) # this is gonna return an expression node
            # return res, ret???
            # If you do return res, ret for run_expr you need to do it for all cases

        elif kind in self.bops:

            if eager == False:
                new_expr = copy.deepcopy(expr)
                new_expr.dict['op1'] = self.run_expr(new_expr.dict['op1'], eager=False)[0]
                new_expr.dict['op2'] = self.run_expr(new_expr.dict['op2'], eager=False)[0]
                return new_expr, ret

            if kind == '&&' or kind == '||': # short circuit
                l, ret = self.run_expr(expr.get('op1'), eager=True)
                # while type(l) == Element and type(ret) != str: l, ret = self.run_expr(l, eager=True)
                if type(ret) == str: return l, ret
                tl = type(l)
                if tl == bool:
                    if kind == '&&' and not l: return False, ret # l is false
                    if kind == '||' and l: return True, ret # l is true
                    r, ret = self.run_expr(expr.get('op2'), eager=True) # l doesn't matter now
                    # while type(r) == Element and type(ret) != str: r, ret = self.run_expr(r, eager=True)
                    if type(ret) == str: return r, ret
                    tr = type(r)
                    if tr == bool: return r, ret
                super().error(ErrorType.TYPE_ERROR, '&& or || wrong type')


            l, ret = self.run_expr(expr.get('op1'), eager=True)
            # eagerness should propogate
            # while type(l) == Element and type(ret) != str: l, ret = self.run_expr(l, eager=True) # infinite loop
            if type(ret) == str: return l, ret
            r, ret = self.run_expr(expr.get('op2'), eager=True)
            # while type(r) == Element and type(ret) != str: r, ret = self.run_expr(r, eager=True)
            if type(ret) == str: return r, ret
            tl, tr = type(l), type(r)

            # ret has to be False now

            if kind == '==': return tl == tr and l == r, ret
            if kind == '!=': return not (tl == tr and l == r), ret

            if tl == str and tr == str:
                if kind == '+': return l + r, ret

            if tl == int and tr == int:
                if kind == '+': return l + r, ret
                if kind == '-': return l - r, ret
                if kind == '*': return l * r, ret
                if kind == '/': return (None, "div0") if r == 0 else (l // r, ret)
                if kind == '<': return l < r, ret
                if kind == '<=': return l <= r, ret
                if kind == '>': return l > r, ret
                if kind == '>=': return l >= r, ret
            
            if tl == bool and tr == bool:
                if kind == '&&': return l and r, ret
                if kind == '||': return l or r, ret

            super().error(ErrorType.TYPE_ERROR, '')

        elif kind == 'neg':
            if eager == False:
                new_expr = copy.deepcopy(expr)
                new_expr.dict['op1'] = self.run_expr(new_expr.dict['op1'], eager=False)[0]
                return new_expr, ret
            o, ret = self.run_expr(expr.get('op1'), eager=True)
            # while type(o) == Element and type(ret) != str: o, ret = self.run_expr(o, eager=True)
            if type(o) == int or type(ret) == str: return -o, ret
            
            super().error(ErrorType.TYPE_ERROR, '')

        elif kind == '!':
            if eager == False:
                new_expr = copy.deepcopy(expr)
                new_expr.dict['op1'] = self.run_expr(new_expr.dict['op1'], eager=False)[0]
                return new_expr, ret
            o, ret = self.run_expr(expr.get('op1'), eager=True)
            # while type(o) == Element and type(ret) != str: o, ret = self.run_expr(o, eager=True)
            if type(o) == bool or type(ret) == str: return not o, ret

            super().error(ErrorType.TYPE_ERROR, '')

        return None, None

def main():
    interpreter = Interpreter()

    with open('./test.br', 'r') as f:
        program = f.read()

    print(parse_program(program))

    interpreter.run(program)

if __name__ == '__main__':
    main()
