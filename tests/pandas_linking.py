from pandas import DataFrame


class MyObj:

    def __init__(self, x, y):

        self.x = x
        self.y = y


# create a list of objects
objects = list()
for i in range(1, 5):
    objects.append(MyObj(i, i**2))


# create the DataFrame and print it
# data = list()
# for obj in objects:
#     data.append([obj.x, obj.y])
#
# df = DataFrame(data=data, columns=['x', 'y'])
# print('\nDataFrame content (prev)')
# print(df)
#
# # now change the df, and check the objects
# df.values[3, 1] = 66
# print('\nDataFrame content (post)')
# print(df)
#
#
# print('\nobjects content (post)')
# for obj in objects:
#     print([obj.x, obj.y])

df = DataFrame(data=objects, columns=['x'])
print('\nDataFrame content (prev)')
print(df)