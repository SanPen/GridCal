# External functions
def f1(instance):
    return f"f1 called with {instance}"


def f2(instance):
    return f"f2 called with {instance}"


def f3(instance):
    return f"f3 called with {instance}"


# The class
class MyClass:
    def create_lambdas(self):
        # List of external functions
        functions = [f1, f2, f3]
        lambdas = []

        for func in functions:
            print(f"Assigning function: {func}")  # Debug output
            # Create lambda to capture the current function and pass `self`
            lambdas.append(lambda func=func: func(self))

        return lambdas


# Usage
my_instance = MyClass()
lambdas = my_instance.create_lambdas()

for l in lambdas:
    print(l())
