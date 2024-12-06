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

        _, ret = self.run_fcall(self.funcs[main_key], eager=False)
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
                res, ret = self.run_expr(statement.get('expression'), eager=False) # this shouldn't happen b/c of lazy nonevaluation
                # or you could change what run_expr returns (it could be an expression node or smth)
                # current idea: for run_assign, make a copy of the AST expression node and then replace all the variables
                # in the expression node with a copy of their values
                # then, when you eagerly evaluate, you have the proper "state" when x was assigned
                # if type(ret) == str: return res, ret
                scope_vars[name] = res
                return None, None

            if is_func: break

        super().error(ErrorType.NAME_ERROR, '')

    def run_fcall(self, statement, eager):
        fcall_name, args = statement.get('name'), statement.get('args')

        res, ret = None, None

        if fcall_name == 'inputi' or fcall_name == 'inputs':
            if len(args) > 1:
                super().error(ErrorType.NAME_ERROR, '')

            if args:
                res, ret = self.run_expr(args[0], eager=True) # SHOUDL THIS BE EAGER EVALUATION?
                if type(ret) == str: return res, ret
                super().output(str(res))

            res = super().get_input()

            return (int(res), None) if fcall_name == 'inputi' else (res, None)

        if fcall_name == 'print':
            
            out = ''

            for arg in args:
                c_out, ret = self.run_expr(arg, eager=True)
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
        res, ret = self.run_statements(func_def.get('statements'), eager=eager)
        self.vars.pop()
        return res, ret

    def run_if(self, statement, eager):
        cond, ret = self.run_expr(statement.get('condition'), eager=True) # should be eager evaluation
        if type(ret) == str: return cond, ret

        if type(cond) != bool:
            super().error(ErrorType.TYPE_ERROR, '')

        self.vars.append(({}, False, []))

        res, ret = None, False

        if cond:
            res, ret = self.run_statements(statement.get('statements'), eager=eager)
        elif statement.get('else_statements'):
            res, ret = self.run_statements(statement.get('else_statements'), eager=eager)

        self.vars.pop()

        return res, ret

    def run_for(self, statement, eager):
        res, ret = None, False

        _, rai = self.run_assign(statement.get('init'))
        if type(rai) == str: return _, rai

        while True:
            cond, rai = self.run_expr(statement.get('condition'), eager=True) # should be eager evaluation
            if type(rai) == str: return res, rai

            if type(cond) != bool:
                super().error(ErrorType.TYPE_ERROR, '')

            if ret == True or not cond: break

            self.vars.append(({}, False, []))
            res, ret = self.run_statements(statement.get('statements'), eager=eager)
            self.vars.pop()

            _, rai = self.run_assign(statement.get('update')) # should be lazy evaluation
            if type(rai) == str: return _, rai

        return res, ret
    
    def run_try(self, statement, eager):
        res, ret = None, False
        self.vars.append(({}, False, []))
        res, ret = self.run_statements(statement.get('statements'), eager=eager)
        self.vars.pop()
        if type(ret) != str: return res, ret
        for catcher in statement.get('catchers'):
            if catcher.get('exception_type') == ret:
                self.vars.append(({}, False, []))
                res, ret = self.run_statements(catcher.get('statements'), eager=eager)
                self.vars.pop()
                break
        return res, ret

    def run_return(self, statement, eager):
        expr = statement.get('expression')
        # res, ret = self.run_expr(expr, eager=True) # fix this?
        # According to spec, the expressions in return statements are evaluated lazily.
        # eagerness should propogate
        if expr:
            if eager:
                return self.run_expr(expr, eager=eager)
            res, ret = self.run_expr(expr, eager=eager)
            return res, ret
            # print("NOT EAGER EXPR", res, ret)
        return None, True
    
    def run_raise(self, statement):
        expr = statement.get('exception_type')
        res, ret = self.run_expr(expr, eager=True) # should be eager evaluation
        if type(ret) == str: return res, ret # case where exception_type is a raise
        if type(res) == str: return None, res # case where exception_type is a string
        super().error(ErrorType.TYPE_ERROR, '')
        

    def run_statements(self, statements, eager=True):
        res, ret = None, False # do i need to add raise here?

        for statement in statements:
            kind = statement.elem_type

            if kind == 'vardef':
                self.run_vardef(statement)
            elif kind == '=':
                _, ret = self.run_assign(statement)
            elif kind == 'fcall':
                _, ret =  self.run_fcall(statement, eager=False) # fcall can raise something
                if ret == True: ret = None
            elif kind == 'if':
                res, ret = self.run_if(statement, eager=eager) # if can raise something
            elif kind == 'for':
                res, ret = self.run_for(statement, eager=eager) # for can raise something
            elif kind == 'try':
                res, ret = self.run_try(statement, eager=eager)
            elif kind == 'return':
                res, rai = self.run_return(statement, eager=eager) # fix this?
                if type(rai) == str: return res, rai
                ret = True
            elif kind == 'raise':
                res, ret = self.run_raise(statement) # fix this?

            if ret == True or type(ret) == str: break


        return res, ret
    
    def modify(self, expr, res):
        res_type = type(res)
        expr.dict['val'] = res
        if res_type == int:
            expr.elem_type = 'int'
        elif res_type == str:
            expr.elem_type = 'string'
        elif res_type == bool:
            expr.elem_type = 'bool'
        # expr.dict.pop('op1', None)
        # expr.dict.pop('op2', None)
        # expr.dict.pop('args', None)
        # expr.dict.pop('name', None)

    def run_expr(self, expr, eager):
        if expr == None: return None, None
        kind = expr.elem_type

        # put in a case for lazy nonevaluation of expressions and eager evaluation of expressions
        # eager evaluation can have multiple layers to it, causing a cascade of eager evaluations

        res, ret = None, None

        if kind == 'int' or kind == 'string' or kind == 'bool':
            if eager == False: return (expr), ret
            return expr.get('val'), ret # ret must be none

        elif kind == 'nil':
            if eager == False: return (expr), ret
            return None, ret

        elif kind == 'var':
            var_name = expr.get('name')

            for scope_vars, is_func, _ in self.vars[::-1]:
                if var_name in scope_vars:
                    scope_vars[var_name].varRef = True
                    if eager == False:
                        return scope_vars[var_name], ret
                    res, ret = self.run_expr(scope_vars[var_name], eager=True) # res can be a normal number or an expression node
                    self.modify(scope_vars[var_name], res)
                    return res, ret

                if is_func: break

            if eager == False:
                return expr, None

            super().error(ErrorType.NAME_ERROR, '')

        elif kind == 'fcall':
            if eager == False:
                new_expr = copy.deepcopy(expr) 
                argList = new_expr.dict['args']
                for i in range(len(argList)): argList[i] = self.run_expr(argList[i], eager=False)[0] # we can do res, ret but ret should always be None right?
                return new_expr, ret
            res, ret = self.run_fcall(expr, eager=True)
            if hasattr(expr, 'varRef'): self.modify(expr, res) # this messes things up, only modify if the fcall is a variable name

            return res, ret # this is gonna return an expression node
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
                if type(ret) == str: return None, ret
                tl = type(l)
                if tl == bool:
                    if kind == '&&' and not l:
                        res, ret = False, ret
                        if hasattr(expr, 'varRef'): self.modify(expr, res)
                        return False, ret # l is false
                    if kind == '||' and l:
                        res, ret = True, ret
                        if hasattr(expr, 'varRef'): self.modify(expr, res)
                        return True, ret # l is true
                    r, ret = self.run_expr(expr.get('op2'), eager=True) # l doesn't matter now
                    tr = type(r)
                    if tr == bool:
                        res, ret = r, ret
                        if hasattr(expr, 'varRef'): self.modify(expr, res)
                        return r, ret
                super().error(ErrorType.TYPE_ERROR, '&& or || wrong type')

            l, ret = self.run_expr(expr.get('op1'), eager=True)
            # eagerness should propogate
            if type(ret) == str: return l, ret
            r, ret = self.run_expr(expr.get('op2'), eager=True)
            if type(ret) == str: return r, ret
            tl, tr = type(l), type(r)

            # ret has to be False now

            if kind == '==':
                res, ret = tl == tr and l == r, ret
                if hasattr(expr, 'varRef'): self.modify(expr, res)
                return tl == tr and l == r, ret
            if kind == '!=':
                res, ret = not (tl == tr and l == r), ret
                if hasattr(expr, 'varRef'): self.modify(expr, res)
                return not (tl == tr and l == r), ret

            if tl == str and tr == str:
                if kind == '+':
                    res, ret = l + r, ret
                    if hasattr(expr, 'varRef'): self.modify(expr, res)
                    return l + r, ret

            if tl == int and tr == int:
                if kind == '+':
                    res, ret = l + r, ret
                    if hasattr(expr, 'varRef'): self.modify(expr, res)
                    return l + r, ret
                if kind == '-':
                    res, ret = l - r, ret
                    if hasattr(expr, 'varRef'): self.modify(expr, res)
                    return l - r, ret
                if kind == '*': 
                    res, ret = l * r, ret
                    if hasattr(expr, 'varRef'): self.modify(expr, res)
                    return l * r, ret
                if kind == '/':
                    if r == 0: return (None, "div0")
                    res, ret = l // r, ret
                    if hasattr(expr, 'varRef'): self.modify(expr, res)
                    return l // r, ret
                if kind == '<':
                    res, ret = l < r, ret
                    if hasattr(expr, 'varRef'): self.modify(expr, res)
                    return l < r, ret
                if kind == '<=':
                    res, ret = l <= r, ret
                    if hasattr(expr, 'varRef'): self.modify(expr, res)
                    return l <= r, ret
                if kind == '>':
                    res, ret = l > r, ret
                    if hasattr(expr, 'varRef'): self.modify(expr, res)
                    return l > r, ret
                if kind == '>=':
                    res, ret = l >= r, ret
                    if hasattr(expr, 'varRef'): self.modify(expr, res)
                    return l >= r, ret
            
            if tl == bool and tr == bool:
                if kind == '&&':
                    res, ret = l and r, ret
                    if hasattr(expr, 'varRef'): self.modify(expr, res)
                    return l and r, ret
                if kind == '||':
                    res, ret = l or r, ret
                    if hasattr(expr, 'varRef'): self.modify(expr, res)
                    return l or r, ret

            super().error(ErrorType.TYPE_ERROR, '')

        elif kind == 'neg':
            if eager == False:
                new_expr = copy.deepcopy(expr)
                new_expr.dict['op1'] = self.run_expr(new_expr.dict['op1'], eager=False)[0]
                return new_expr, ret
            o, ret = self.run_expr(expr.get('op1'), eager=True)
            if type(o) == int or type(ret) == str:
                res, ret = -o, ret
                if hasattr(expr, 'varRef'): self.modify(expr, res)
                return -o, ret
            
            super().error(ErrorType.TYPE_ERROR, '')

        elif kind == '!':
            if eager == False:
                new_expr = copy.deepcopy(expr)
                new_expr.dict['op1'] = self.run_expr(new_expr.dict['op1'], eager=False)[0]
                return new_expr, ret
            o, ret = self.run_expr(expr.get('op1'), eager=True)
            if type(o) == bool or type(ret) == str:
                res, ret = not o, ret
                if hasattr(expr, 'varRef'): self.modify(expr, res)
                return not o, ret

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
