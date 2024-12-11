variables = [
"Vm", "Va", "P_f^{vsc}", "P_t^{vsc}", "Q_t^{vsc}", "P_f^{hvdc}", "P_t^{hvdc}", "Q_f^{hvdc}", "Q_t^{hvdc}", "m", "\\tau"
]

rhs = [
    "P", "Q", "loss_{vsc}", "loss_{hvdc}", "inj_{hvdc}", "P_f", "P_t", "Q_f", "Q_t"
]

p = r"""\frac{\partial A}{\partial B}"""

for i, r in enumerate(rhs):
    for j, v in enumerate(variables):
        d = p.replace("A", r).replace("B", v)

        if j < len(variables) - 1:
            d += " & "

        print(d, end="")

    if i < len(rhs) - 1:
        print(r" \\")
