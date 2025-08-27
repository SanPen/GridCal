This is the complicated delete logic from the Schematic and the Map
This logic is best observed in the base_diagram_widget.py

`delete_selected_from_widget`
        |
        |
         -----> `delete_with_dialogue`
                        |
                        |----> `DeleteDialogue`
                        |
                         ----> `remove_element`
                                    |
                                    |
                                     ----> `_remove_from_scene` (Actually removing the Qt object from the scene)
                                    |
                                     ----> `remove_element` (recursive)                                    
                                    |
                                     ----> `delete_element_utility_function` (delete in other diagrams through the GUI)
                                                    |
                                                     ----> `graphic_obj.get_associated_graphics` (gets a list of other graphics that must be deleted along)
                                                    |
                                                     ----> `gui.call_delete_db_element`  (call to delete from the DB is necessary)
                                                    |
                                                     ----> `_remove_from_scene` (necessary to exist here too because of the callback)
                                                    |
                                                     ----> `graphics_manager.delete_device` (deletes from the diagram registry)
                                                    |
                                                     ----> `diagram.delete_devic` (remove from the diagram object)