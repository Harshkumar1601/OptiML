# Restricted C-Like Language — Formal Grammar

This document defines the BNF grammar implemented in `compiler/lexer.py` and `compiler/parser.py`.

---

## Token Set

### Keywords
```
int  float  if  else  while  for  return
```

### Comments (silently discarded by lexer)
```
// single-line comment
/* multi-line block comment */
```

### Operators
```
+   -   *   /                  (arithmetic)
<   >   <=  >=  ==  !=         (relational)
&&  ||                         (logical, conditions only)
=                              (assignment)
```

### Delimiters
```
(  )  {  }  ;  ,
```

### Literals
```
INTEGER_LITERAL   ::= [0-9]+
FLOAT_LITERAL     ::= [0-9]+ '.' [0-9]+
```

### Identifiers
```
IDENTIFIER        ::= [a-zA-Z_][a-zA-Z0-9_]*
```

---

## Grammar Rules (BNF)

```bnf
program         ::= function_list

function_list   ::= function_def
                  | function_list function_def

function_def    ::= type IDENTIFIER '(' param_list ')' block
                  | type IDENTIFIER '(' ')' block

param_list      ::= param
                  | param_list ',' param

param           ::= type IDENTIFIER

type            ::= 'int'
                  | 'float'

block           ::= '{' stmt_list '}'
                  | '{' '}'

stmt_list       ::= stmt
                  | stmt_list stmt

stmt            ::= declaration ';'
                  | assignment ';'
                  | if_stmt
                  | while_stmt
                  | for_stmt
                  | return_stmt ';'
                  | func_call ';'

declaration     ::= type IDENTIFIER
                  | type IDENTIFIER '=' expr

assignment      ::= IDENTIFIER '=' expr

if_stmt         ::= 'if' '(' condition ')' block
                  | 'if' '(' condition ')' block 'else' block

while_stmt      ::= 'while' '(' condition ')' block

for_stmt        ::= 'for' '(' for_init ';' condition ';' for_update ')' block

for_init        ::= declaration
                  | assignment

for_update      ::= assignment

return_stmt     ::= 'return' expr
                  | 'return'

func_call       ::= IDENTIFIER '(' arg_list ')'
                  | IDENTIFIER '(' ')'

arg_list        ::= expr
                  | arg_list ',' expr

condition       ::= expr rel_op expr
                  | condition '&&' condition
                  | condition '||' condition

rel_op          ::= '<' | '>' | '<=' | '>=' | '==' | '!='

expr            ::= expr '+' term
                  | expr '-' term
                  | term

term            ::= term '*' factor
                  | term '/' factor
                  | factor

factor          ::= '(' expr ')'
                  | '-' factor           (* unary minus *)
                  | IDENTIFIER
                  | INTEGER_LITERAL
                  | FLOAT_LITERAL
                  | func_call
```

---

## Operator Precedence (Lowest to Highest)

| Level | Operators |
|---|---|
| 1 (lowest) | `\|\|` |
| 2 | `&&` |
| 3 | `==` `!=` |
| 4 | `<` `>` `<=` `>=` |
| 5 | `+` `-` |
| 6 | `*` `/` |
| 7 (highest) | Unary `-` (right-assoc), parentheses |

---

## Design Decisions (Confirmed)

| Decision | Choice |
|---|---|
| Unary minus | Supported via `factor ::= '-' factor` (right-recursive) |
| Bare-expression conditions | NOT supported — relational operator always required |
| `for` increment shorthand (`i++`) | NOT supported — use `i = i + 1` |
| Comments | `//` single-line and `/* */` block comments — both silently discarded by lexer |

## Language Restrictions (Intentional)

The following are NOT supported by design:
- Arrays, pointers, structs
- `char`, `string` types
- `#include`, `#define`, preprocessor directives
- `switch`, `do-while`, `break`, `continue`
- Dynamic memory (`malloc`, `free`)
- Type casting
- Global variables (all variables declared inside functions)
- Bare boolean conditions: `if (x)` is invalid; write `if (x != 0)` instead
- Increment/decrement operators (`i++`, `i--`, `++i`): write `i = i + 1`
