import ast_generator as  A
import chat

if __name__ == "__main__":
    """
            please note if the function is a class method, for example A.B
            adding one line here is neccesity(as below):
            A.class_stack.append(class_obj)
       
    """
    module_map = A.get_namespace(chat.ChatAgent.invoke)
    A.class_stack.append(chat.ChatAgent)
    tree = A.dot_source_prepare(chat.ChatAgent.invoke)
    A.add_nodes_edges(tree, current_graph = A.dot,potential_module_map = module_map)
    A.save_ast("ast_demo")