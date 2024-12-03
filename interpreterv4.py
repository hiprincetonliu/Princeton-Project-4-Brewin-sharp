
from intbase import InterpreterBase, ErrorType
from brewparse import parse_program

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

        if name in self.vars[-1][0]:
            super().error(ErrorType.NAME_ERROR, '')

        self.vars[-1][0][name] = None

    def run_assign(self, statement):
        name = statement.get('name')

        for scope_vars, is_func in self.vars[::-1]:
            if name in scope_vars:
                res, ret = self.run_expr(statement.get('expression'))
                if type(ret) == str: return res, ret
                scope_vars[name] = res
                return

            if is_func: break

        super().error(ErrorType.NAME_ERROR, '')

    def run_fcall(self, statement):
        fcall_name, args = statement.get('name'), statement.get('args')

        res, ret = None, None

        if fcall_name == 'inputi' or fcall_name == 'inputs':
            if len(args) > 1:
                super().error(ErrorType.NAME_ERROR, '')

            if args:
                res, ret = self.run_expr(args[0])
                if type(ret) == str: return res, ret
                super().output(str(res))

            res = super().get_input()

            return (int(res), None) if fcall_name == 'inputi' else (res, None)

        if fcall_name == 'print':
            out = ''

            for arg in args:
                c_out, ret = self.run_expr(arg)
                if type(ret) == str: return c_out, ret
                if type(c_out) == bool:
                    out += str(c_out).lower()
                else:
                    out += str(c_out)

            super().output(out)

            return None, None
        
        if (fcall_name, len(args)) not in self.funcs:
            super().error(ErrorType.NAME_ERROR, '')

        func_def = self.funcs[(fcall_name, len(args))]

        template_args = [a.get('name') for a in func_def.get('args')]
        passed_args = []
        for a in args:
            res, ret = self.run_expr(a)
            if type(ret) == str: return res, ret
            passed_args.append(res)

        self.vars.append(({k:v for k,v in zip(template_args, passed_args)}, True))
        res, ret = self.run_statements(func_def.get('statements'))
        self.vars.pop()

        return res, ret
        return res # return res, ret???

    def run_if(self, statement):
        cond, ret = self.run_expr(statement.get('condition'))
        if type(ret) == str: return cond, ret

        if type(cond) != bool:
            super().error(ErrorType.TYPE_ERROR, '')

        self.vars.append(({}, False))

        res, ret = None, False

        if cond:
            res, ret = self.run_statements(statement.get('statements'))
        elif statement.get('else_statements'):
            res, ret = self.run_statements(statement.get('else_statements'))

        self.vars.pop()

        return res, ret

    def run_for(self, statement):
        res, ret = None, False

        self.run_assign(statement.get('init'))

        while True:
            cond, rai = self.run_expr(statement.get('condition'))
            if type(rai) == str: return res, rai

            if type(cond) != bool:
                super().error(ErrorType.TYPE_ERROR, '')

            if ret == True or not cond: break

            self.vars.append(({}, False))
            res, ret = self.run_statements(statement.get('statements'))
            self.vars.pop()

            self.run_assign(statement.get('update'))

        return res, ret

    def run_return(self, statement):
        expr = statement.get('expression')
        if expr:
            res, ret = self.run_expr(expr)
            if type(ret) == str: return res, ret
            return res, ret
        return None, True
    
    def run_raise(self, statement):
        expr = statement.get('exception_type')
        expr, ret = self.run_expr(expr)
        if type(ret) == str: return expr, ret # case where exception_type is a raise
        t_expr = type(expr)
        if t_expr == str: return None, expr
        super().error(ErrorType.TYPE_ERROR, '')
        

    def run_statements(self, statements):
        res, ret = None, False # do i need to add raise here?

        for statement in statements:
            kind = statement.elem_type

            if kind == 'vardef':
                self.run_vardef(statement)
            elif kind == '=':
                self.run_assign(statement)
            elif kind == 'fcall':
                _, ret =  self.run_fcall(statement) # fcall can raise something
                if type(ret) == str: break # ret has to be a string???
            elif kind == 'if':
                res, ret = self.run_if(statement) # if can raise something
                if ret: break
                if type(ret) == str: break
            elif kind == 'for':
                res, ret = self.run_for(statement) # for can raise something
                if ret: break
                if type(ret) == str: break
            elif kind == 'return':
                res, rai = self.run_return(statement) # fix this?
                if type(rai) == str: return res, rai
                ret = True
                break
            elif kind == 'raise':
                res = None
                ret = False
                res, ret = self.run_raise(statement) # fix this?
                break


        return res, ret

    def run_expr(self, expr):
        kind = expr.elem_type

        res, ret = None, None

        if kind == 'int' or kind == 'string' or kind == 'bool':
            return expr.get('val'), ret # ret must be none

        elif kind == 'var':
            var_name = expr.get('name')

            for scope_vars, is_func in self.vars[::-1]:
                if var_name in scope_vars:
                    return scope_vars[var_name], ret # ret must be none

                if is_func: break

            super().error(ErrorType.NAME_ERROR, '')

        elif kind == 'fcall':
            res, ret = self.run_fcall(expr)
            if type(ret) == str: return res, ret
            return res, ret # fcall can raise something
            # return res, ret???
            # If you do return res, ret for run_expr you need to do it for all cases

        elif kind in self.bops:

            if kind == '&&' or kind == '||': # short circuit
                l, ret = self.run_expr(expr.get('op1'))
                if type(ret) == str: return l, ret
                tl = type(l)
                if tl == bool:
                    if kind == '&&' and not l: return False, ret # l is false
                    if kind == '||' and l: return True, ret # l is true
                    r, ret = self.run_expr(expr.get('op2')) # l doesn't matter now
                    if type(ret) == str: return r, ret
                    tr = type(r)
                    if tr == bool: return r, ret
                super().error(ErrorType.TYPE_ERROR, '&& or || wrong type')

            l, ret = self.run_expr(expr.get('op1'))
            if type(ret) == str: return l, ret
            r, ret = self.run_expr(expr.get('op2'))
            if type(ret) == str: return r, ret
            tl, tr = type(l), type(r)

            if kind == '==': return tl == tr and l == r, ret
            if kind == '!=': return not (tl == tr and l == r), ret

            if tl == str and tr == str:
                if kind == '+': return l + r, ret

            if tl == int and tr == int:
                if kind == '+': return l + r, ret
                if kind == '-': return l - r, ret
                if kind == '*': return l * r, ret
                if kind == '/': return l // r, ret
                if kind == '<': return l < r, ret
                if kind == '<=': return l <= r, ret
                if kind == '>': return l > r, ret
                if kind == '>=': return l >= r, ret
            
            if tl == bool and tr == bool:
                if kind == '&&': return l and r, ret
                if kind == '||': return l or r, ret

            super().error(ErrorType.TYPE_ERROR, '')

        elif kind == 'neg':
            o, ret = self.run_expr(expr.get('op1'))
            if type(ret) == str: return o, ret
            if type(o) == int: return -o, ret
            
            super().error(ErrorType.TYPE_ERROR, '')

        elif kind == '!':
            o, ret = self.run_expr(expr.get('op1'))
            if type(ret) == str: return o, ret
            if type(o) == bool: return not o, ret

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
