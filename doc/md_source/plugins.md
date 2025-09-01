# 🧩 Plugins

You can write your own Plugin for VeraGrid, and it will create an entry in the plugins menu with
your custom icon if you desire so.

First navigate to the VeraGrid user folder. If you don't know where that is, type `user_folder()`
on VeraGrid's scripting console. Usually it is located in a folder called `.VeraGrid` on your user folder.

Inside the `.VeraGrid` folder you will find a folder called `plugins`.
For each plugin that we want to have, need three files in there to declare our plugin. 
The files are:

- `plugins.plugin.json`: This is the plugin declaration file. It is a JSON file where you add your plugin information.
- `plugin1.py`: This is where you write your plugin.
- `icon1.svg`: This is your icon to display in the plugins drop-down menu. You can create it with a design program such as InkScape.


The content of `plugins.plugin.json` is:

```json

    {
        "name": "my_plugin1",
        "path": "plugin1.py",
        "icon_path": "icon1.svg",
        "main_fcn": {
                        "name": "main",
                        "alias": "my function 1"
                    },
        "investments_fcn": {
                        "name": "investments",
                        "alias": "investments function 1"
                    }
    }
```

The four parameters that we must specify are:

- `name`: Name of the plugin to be displayed and referred to by VeraGrid.
- `path`: Path of the plugin file relative to the base folder `.VeraGrid/plugins`.
- `icon_path`: Path of the SVG icon that you want to use. you can leave the field blank and VeraGrid will use an internal icon.
- `main_fcn`: Entry to declare the main function of the plugin accessible from the `plugins`menu in the user interface.
- `investments_fcn`: (optional) this is a custom function to be called with the investments.


The content of `plugin1.py` is:

```python
    from VeraGrid.Gui.Main.VeraGridMain import MainGUI
from VeraGridEngine.api import InvestmentsEvaluationDriver


def main(gui_instance: MainGUI):
    """
    Initial plugin function
    :param gui_instance: Instance of the VeraGrid GUI object
    """
    print("Hello from plugin1!")

    grid = gui_instance.circuit

    for bus in grid.buses:
        print(bus.name)


def investments(driver: InvestmentsEvaluationDriver):
    """
    Implement the logic that launches for my custom investment
    """
    print("Investments driver name: " + driver.name)
```


This is a very simple example. However, the function that you set as the starting 
point of your plugin must accept only one argument of type `MainGUI`. 
See the function `main` in the code above. This is because VeraGrid will pass "itself"
into the plugin so that you can acquire total control and access to do whatever 
you want to do from the plugin. Of course, with great power comes great responsibility.


## Installation of a plugin

A VeraGrid plugin ends with `.vgplugin`. 
You just need to drag & drop that plugin file into the user interface. 