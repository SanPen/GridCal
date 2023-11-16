# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
from enum import Enum


class Colormaps(Enum):
    GridCal = 'GridCal'
    TSO = 'TSO'  # -1, 1
    TSO2 = 'TSO 2'  # -1, 1
    SCADA = 'SCADA'  # -1, 1
    Heatmap = 'Heatmap'  # 0, 1
    Blues = 'Blue'  # 0, 1
    Greens = 'Green'  # 0, 1
    Blue2Gray = 'Blue to gray'  # 0, 1
    Green2Red = 'Green to red'  # -1, 1
    Red2Blue = 'Red to blue'  # -1, 1


def tso2_line_palette_bgr(x, warning_lvl=0.9, overload_lvl=1.15):
    """
    use TSO2 color scheme for people not to freak out
    Get RGB color from value
    :param x: value of loading in p.u.
    :param warning_lvl: Value of warning (i.e. 80%-> 0.8)
    :param overload_lvl: Value of overload (i.e. 110%-> 1.1)
    :return: BGR color
    """
    if x <= -overload_lvl:
        return 7, 7, 240  # red

    elif -overload_lvl < x <= -warning_lvl:
        return 0, 180, 255  # yellow

    elif -warning_lvl <= x < warning_lvl:
        return 0, 184, 127  # green

    elif warning_lvl <= x < overload_lvl:
        return 0, 180, 255  # yellow

    elif overload_lvl <= x:
        return 7, 112, 0  # red

    else:
        return 50, 50, 50  # gray (impossible, but who knows..)


def rgb2bgr(color):
    return color[2], color[1], color[0]


def tso_substation_palette_bgr(x):
    """
    Get the classic Substation colors
    :param x: Substation voltage in kV
    :return: BGR
    """
    if x >= 400:
        color = (0, 57, 242)  # (242, 57, 0, 255)  # 'red'
    elif 150 <= x <= 220:
        color = (54, 181, 19)  # (19, 181, 54, 255)  # 'green'
    else:
        color = (0, 0, 0)  # 'black'

    return color


def tso_line_palette_bgr(v, loading, warning_lvl=0.9, overload_lvl=1.15):
    """
    Get the classic Substation colors
    :param v: line voltage in kV
    :param loading: loading in p.u.
    :param warning_lvl: Warning level
    :param overload_lvl: Overload level
    :return: BGR
    """

    '''
    3 niveles de rojo
    •	RGB 205,97,85                 <50%
    •	RGB 192,57,43                  
    •	RGB 123,36,28                 >85%
    
    3 niveles de verde
    •	RGB 125,206,160               <50%
    •	RGB 39,174,96                  
    •	RGB 25,111,61                 >85%    
    '''

    if v >= 400:

        if loading < warning_lvl:
            return 177, 183, 245
        elif warning_lvl <= loading <= overload_lvl:
            return 43, 57, 192
        elif loading > overload_lvl:
            return 22, 30, 100
        else:
            return 0, 57, 242  # (242, 57, 0, 255)  # 'red'

    elif 150 <= v <= 220:

        if loading < warning_lvl:
            return 191, 223, 169
        elif warning_lvl <= loading <= overload_lvl:
            return 96, 174, 39
        elif loading > overload_lvl:
            return 50, 90, 20
        else:
            return 54, 181, 19  # (19, 181, 54, 255)  # 'green'

    else:
        color = (0, 0, 0)  # 'black'

    return color


def heatmap_palette_bgr(x):
    """
    Heatmap colors
    :param x: [0, 1]
    :return: BGR
    """
    if 0 <= x < 0.125:
        return 92, 63, 0
    elif 0.125 <= x < 0.25:
        return 124, 75, 47
    elif 0.25 <= x < 0.375:
        return 145, 81, 102
    elif 0.375 <= x < 0.5:
        return 149, 81, 160
    elif 0.5 <= x < 0.625:
        return 135, 80, 212
    elif 0.625 <= x < 0.75:
        return 106, 93, 249
    elif 0.75 <= x < 0.875:
        return 67, 124, 255
    elif 0.875 <= x <= 1:
        return 0, 166, 255
    else:
        return 50, 50, 50


def blues_palette_bgr(x):
    """
    Blues palette
    :param x: [0, 1]
    :return: BGR
    """
    if 0 <= x < 0.166666666666667:
        return 109, 76, 0
    elif 0.166666666666667 <= x < 0.333333333333333:
        return 136, 104, 52
    elif 0.333333333333333 <= x < 0.5:
        return 165, 134, 88
    elif 0.5 <= x < 0.666666666666667:
        return 194, 166, 122
    elif 0.666666666666667 <= x < 0.833333333333333:
        return 224, 198, 157
    elif 0.833333333333333 <= x <= 1:
        return 255, 231, 193


def greens_palette_bgr(x):
    """
    Greens palette
    :param x: [0, 1]
    :return: BGR
    """
    if 0 <= x < 0.2:
        return 255, 70, 19
    elif 0.2 <= x < 0.4:
        return 255, 137, 62
    elif 0.4 <= x < 0.6:
        return 255, 163, 61
    elif 0.6 <= x < 0.8:
        return 255, 224, 150
    elif 0.8 <= x <= 1:
        return 255, 252, 232
    else:
        return 0, 0, 0


def blues_to_gray_bgr(x):
    """
    Blue to gray
    :param x: [0, 1]
    :return: BGR
    """
    if 0 <= x < 0.166666666666667:
        return 109, 76, 0
    elif 0.166666666666667 <= x < 0.333333333333333:
        return 129, 102, 62
    elif 0.333333333333333 <= x < 0.5:
        return 150, 128, 101
    elif 0.5 <= x < 0.666666666666667:
        return 171, 156, 139
    elif 0.666666666666667 <= x < 0.833333333333333:
        return 193, 185, 177
    elif 0.833333333333333 <= x <= 1:
        return 215, 215, 215
    else:
        return 0, 0, 0


def green_to_red_bgr(x):
    """
    Green to red
    :param x: [-1, 1]
    :return: BGR
    """
    if -1 <= x < -0.818181818181818:
        return 108, 135, 0
    elif -0.818181818181818 <= x < -0.636363636363636:
        return 107, 152, 64
    elif -0.636363636363636 <= x < -0.454545454545454:
        return 105, 169, 105
    elif -0.454545454545454 <= x < -0.272727272727273:
        return 104, 184, 145
    elif -0.272727272727273 <= x < -0.0909090909090908:
        return 106, 198, 187
    elif -0.0909090909090908 <= x < 0.0909090909090911:
        return 114, 210, 229
    elif 0.0909090909090911 <= x < 0.272727272727273:
        return 92, 183, 232
    elif 0.272727272727273 <= x < 0.454545454545455:
        return 78, 154, 232
    elif 0.454545454545455 <= x < 0.636363636363636:
        return 72, 125, 230
    elif 0.636363636363636 <= x < 0.818181818181818:
        return 74, 94, 223
    elif 0.818181818181818 <= x <= 1:
        return 81, 61, 212
    else:
        return 0, 0, 0


def red_to_blue_bgr(x):
    """
    BGR Red to Blue
    :param x: [-1, 1]
    :return: BGR
    """
    if x < -1:
        return 255, 65, 249
    elif -1 <= x < -0.75:
        return 255, 65, 249
    elif -0.75 <= x < -0.5:
        return 255, 114, 243
    elif -0.5 <= x < -0.25:
        return 255, 150, 248
    elif -0.25 <= x < 0:
        return 255, 199, 249
    elif 0 <= x < 0.25:
        return 255, 195, 197
    elif 0.25 <= x < 0.5:
        return 255, 190, 144
    elif 0.5 <= x < 0.75:
        return 255, 170, 67
    elif 0.75 <= x <= 1:
        return 255, 117, 87
    elif x > 1:
        return 255, 117, 87
    else:
        return 50, 50, 50


def tso_line_palette_rgb(x):
    """
    use Ree color scheme for people not to freak out
    :param x: [-1, 1]
    :return: RGB
    """
    if -1 <= x < -0.6667:
        return 240, 7, 7
    elif -0.6667 <= x < -0.3334:
        return 255, 180, 0
    elif -0.3334 <= x < -0.0001:
        return 127, 184, 0
    elif -0.0001 <= x < 0.3332:
        return 127, 184, 0
    elif 0.3332 <= x < 0.6665:
        return 255, 180, 0
    elif 0.6665 <= x <= 1.0:
        return 0, 112, 7
    else:
        return 0, 0, 0


def tso_substation_palette_rgb(x):
    """
    Get the classic Substation colors
    :param x: Substation voltage in kV
    :return: RGB
    """
    if 220 > x >= 400:
        color = 242, 57, 0  # 'red'
    elif 150 <= x <= 220:
        color = 19, 181, 54  # 'green'
    else:
        color = 0, 0, 0  # 'black'

    return color


def heatmap_palette_rgb(x):
    """
    Heatmap colors
    :param x: [0, 1]
    :return: RGB
    """
    if 0 <= x < 0.125:
        return 0, 63, 92
    elif 0.125 <= x < 0.25:
        return 47, 75, 124
    elif 0.25 <= x < 0.375:
        return 102, 81, 145
    elif 0.375 <= x < 0.5:
        return 160, 81, 149
    elif 0.5 <= x < 0.625:
        return 212, 80, 135
    elif 0.625 <= x < 0.75:
        return 249, 93, 106
    elif 0.75 <= x < 0.875:
        return 255, 124, 67
    elif 0.875 <= x <= 1:
        return 255, 166, 0
    else:
        return 0, 0, 0


def blues_palette_rgb(x):
    """
    Blues palette
    :param x: [0, 1]
    :return: RGB
    """
    if 0 <= x < 0.166666666666667:
        return 0, 76, 109
    elif 0.166666666666667 <= x < 0.333333333333333:
        return 52, 104, 136
    elif 0.333333333333333 <= x < 0.5:
        return 88, 134, 165
    elif 0.5 <= x < 0.666666666666667:
        return 122, 166, 194
    elif 0.666666666666667 <= x < 0.833333333333333:
        return 157, 198, 224
    elif 0.833333333333333 <= x <= 1:
        return 193, 231, 255
    else:
        return 0, 0, 0


def greens_palette_rgb(x):
    """
    Greens palette
    :param x: [0, 1]
    :return: RGB
    """
    if 0 <= x < 0.2:
        return 19, 70, 255
    elif 0.2 <= x < 0.4:
        return 62, 137, 255
    elif 0.4 <= x < 0.6:
        return 61, 163, 255
    elif 0.6 <= x < 0.8:
        return 150, 224, 255
    elif 0.8 <= x <= 1:
        return 232, 252, 255
    else:
        return 0, 0, 0


def blues_to_gray_rgb(x):
    """
    Blues to gray palette
    :param x: [0, 1]
    :return: RGB
    """
    if 0 <= x < 0.166666666666667:
        return 0, 76, 109
    elif 0.166666666666667 <= x < 0.333333333333333:
        return 62, 102, 129
    elif 0.333333333333333 <= x < 0.5:
        return 101, 128, 150
    elif 0.5 <= x < 0.666666666666667:
        return 139, 156, 171
    elif 0.666666666666667 <= x < 0.833333333333333:
        return 177, 185, 193
    elif 0.833333333333333 <= x <= 1:
        return 215, 215, 215
    else:
        return 0, 0, 0


def green_to_red_rgb(x):
    """
    Green to red palette
    :param x: [-1, 1]
    :return: RGB
    """
    if -1 <= x < -0.818181818181818:
        return 0, 135, 108
    elif -0.818181818181818 <= x < -0.636363636363636:
        return 64, 152, 107
    elif -0.636363636363636 <= x < -0.454545454545454:
        return 105, 169, 105
    elif -0.454545454545454 <= x < -0.272727272727273:
        return 145, 184, 104
    elif -0.272727272727273 <= x < -0.0909090909090908:
        return 187, 198, 106
    elif -0.0909090909090908 <= x < 0.0909090909090911:
        return 229, 210, 114
    elif 0.0909090909090911 <= x < 0.272727272727273:
        return 232, 183, 92
    elif 0.272727272727273 <= x < 0.454545454545455:
        return 232, 154, 78
    elif 0.454545454545455 <= x < 0.636363636363636:
        return 230, 125, 72
    elif 0.636363636363636 <= x < 0.818181818181818:
        return 223, 94, 74
    elif 0.818181818181818 <= x <= 1:
        return 212, 61, 81
    else:
        return 0, 0, 0


def red_to_blue_rgb(x):
    """
    BGR Red to Blue
    :param x: [-1, 1]
    :return: BGR
    """
    if -1 <= x < -0.75:
        return 249, 65, 255
    elif -0.75 <= x < -0.5:
        return 243, 114, 255
    elif -0.5 <= x < -0.25:
        return 248, 150, 255
    elif -0.25 <= x < 0:
        return 249, 199, 255
    elif 0 <= x < 0.25:
        return 197, 195, 255
    elif 0.25 <= x < 0.5:
        return 144, 190, 255
    elif 0.5 <= x < 0.75:
        return 67, 170, 255
    elif 0.75 <= x <= 1:
        return 87, 117, 255
    else:
        return 0, 0, 0
