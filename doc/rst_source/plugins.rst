Plugins
===========

You can write your own Plugin for GridCal, and it will create an entry in the plugins menu with
your custom icon if you desire so.

First navigate to the GridCal user folder. If you don't know where that is, type `user_folder()`
on GridCal's scripting console. Usually it is located in a folder called `.GridCal` on your user folder.

Inside the `.GridCal` folder you will find a folder called `plugins`. We will create some files in there to
declare our plugin. The files are:

- `plugins.json`: This is the plugins index. It is a JSON file where you add your plugin information and should exist there for you.
- `plugin1.py`: This is where you write your plugin.
- `icon1.svg`: This is your icon to display in the plugins drop-down menu. You can create it with a design program such as InkScape.

The content of `plugins.json` is:

.. code-block:: json

    [
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
        },
        {
            "name": "my_plugin2",
            "path": "plugin2.py",
            "icon_path": "icon2.svg",
            "main_fcn": {
                            "name": "main",
                            "alias": "my function 2"
                        },
        }
    ]

The four parameters that we must specify are:

- `name`: Name of the plugin to be displayed and referred to by GridCal.
- `path`: Path of the plugin file relative to the base folder `.GridCal/plugins`.
- `function_name`: Name of the entry point function inside the plugin file.
- `icon_path`: Path of the SVG icon that you want to use. you can leave the field blank and GridCal will use an internal icon.

Of course, we can add more entries for more plugins, following the JSON format.

The content of `plugin1.py` is:

.. code-block:: python

    from GridCal.Gui.Main.GridCalMain import MainGUI
    from GridCalEngine.api import InvestmentsEvaluationDriver


    def main(gui_instance: MainGUI):
        """
        Initial plugin function
        :param gui_instance: Instance of the GridCal GUI object
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




This is a very simple example. However the function that you set as the starting point of your plugin must accept only
one argument of type `MainGUI`. See the function `main` in the code above. This is because GridCal will pass "itself"
into the plugin so that you can acquire total control and access to do whatever you want to do from the plugin.
Of course, with great power comes great responsibility.