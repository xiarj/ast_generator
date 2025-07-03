"""Module used to generate AST graph, using AST and Graphviz
    Example:(import this moudle as A)
        module_map = A.get_namespace(generate_random_data)
            please note if the function is a class method, for example A.B
            add one line here:
            A.class_stack.append(class_obj)
        tree = A.dot_source_prepare(generate_random_data)
        A.add_nodes_edges(tree, current_graph = A.dot,potential_module_map = module_map)
        A.save_ast("this_file")
    only support some gramma in Python, as below:
     Function
     If
     For
     While
     Try
     With
     Match
     Assign
     Return
     Expr
     Continue
     Break
     Call
     Binary Operator
     Unary Operator
     List
     Tuple
    -and some other conditions I don't know if they are supported
    if needed, you can add more gramma to support
    can't correctly unfold functions which are directly imported by from...import, 
    can't correctly unfold module in package, if need, please import them respectively
    didn't deliverately support lambda function,
    calls by any instance object are not supported
        
    version: 0.9
"""
import types
import ast as A
import inspect
import graphviz
import textwrap
import importlib
import sys


dot = graphviz.Digraph(comment='AST Graph')
class_stack = []
def dot_source_prepare(func):
    source = inspect.getsource(func)
    tree = A.parse(textwrap.dedent(source))
    return tree

def add_nodes_edges(node, parent = None, edges_set = None, loop_stack = None, prefix = "",
                     current_graph = None, unfold_times = 2, upper_connect_node = None,
                        end_function_list =[], potential_module_map = []):
    current_graph.attr(rankdir='TB', rank="same")
    if loop_stack is None:
        loop_stack = []
    if edges_set is None:
        edges_set = set()  
    child_iter_needs = True
    
    node_id = f"{prefix}|{id(node)}" 
    # 标记当前节点的ID，供子节点递归时获取
    current_node_id = node_id
    node.current_node_id = current_node_id
    label = node.__class__.__name__
    if isinstance(node, A.Module):
        for child in A.iter_child_nodes(node):
            add_nodes_edges(child, parent, edges_set, loop_stack, prefix, 
                            current_graph, unfold_times, upper_connect_node,
                            end_function_list, potential_module_map)
            return
            
    if isinstance(node, A.FunctionDef):
        if parent is not None:
            parent_id = parent.current_node_id if hasattr(parent, 'current_node_id') else str(id(parent))
            if (parent_id, node_id) not in edges_set:
                current_graph.edge(parent_id, node_id)
                edges_set.add((parent_id, node_id))

        for children in A.iter_child_nodes(node):
            if children not in node.body and children != node.returns:
                child_id = f"{prefix}|{id(children)}"
                children.current_node_id = child_id
                add_nodes_edges(children, node, edges_set, loop_stack, prefix,
                                 current_graph, unfold_times, None, end_function_list, 
                                 potential_module_map)
    
        prev_child = None
        next_child = upper_connect_node
        
        for index, child in enumerate(node.body):
            child_id = f"{prefix}|{id(child)}"
            child.current_node_id = child_id
            if  index == (len(node.body) - 1):
                next_child = upper_connect_node
                if upper_connect_node is not None and not isinstance(child, (A.FunctionDef, A.ClassDef, A.If, A.For, A.While, A.Try, A.With, A.Match)):
                    upper_connect_node_id = upper_connect_node.current_node_id if hasattr(upper_connect_node, 'current_node_id') else str(id(upper_connect_node))
                    edge_label = "Next_Step"
                    if  (child_id, upper_connect_node_id) not in edges_set:
                        dot.edge(child_id, upper_connect_node_id, label = edge_label)
                        edges_set.add((child_id, upper_connect_node_id))
                    
            else:
                next_child = node.body[index + 1]
                next_child_id = f"{prefix}|{id(next_child)}"
                next_child.current_node_id = next_child_id
            if isinstance(child, (A.FunctionDef, A.ClassDef, A.If, A.For, A.While, A.Try, A.With, A.Match)):
                with current_graph.subgraph(name=f"cluster_{child_id}") as c:
                    c.attr(style='solid', penwidth='2', color='lightgreen')              
                    if prev_child is None:
                        prev_child = child
                        if (node_id, child_id) not in edges_set:
                            dot.edge(node_id, child_id)
                            edges_set.add((node_id, child_id))
                            add_nodes_edges(child, node, edges_set, loop_stack, 
                                            prefix, c, unfold_times, next_child,
                                            end_function_list, potential_module_map)
                    else:
                        add_nodes_edges(child, prev_child, edges_set, loop_stack, 
                                        prefix, c, unfold_times, next_child,
                                        end_function_list, potential_module_map)
                        prev_child = child
            else:
                if prev_child is None:
                    prev_child = child
                    if (node_id, child_id) not in edges_set:
                        dot.edge(node_id, child_id)
                        edges_set.add((node_id, child_id))
                        add_nodes_edges(child, node, edges_set, loop_stack, 
                                        prefix, current_graph, unfold_times, next_child,
                                        end_function_list, potential_module_map)
                else:
                    add_nodes_edges(child, prev_child, edges_set, loop_stack, 
                                    prefix, current_graph, unfold_times, next_child,
                                    end_function_list, potential_module_map)
                    prev_child = child
        child_iter_needs = False
        
    if isinstance(node, A.arguments):
        has_arg = False
        for child in A.iter_child_nodes(node):
            for field, value in A.iter_fields(child):
                if field == "arg":
                    label += f"\n{field}: {value!r}"
                    has_arg = True
        if not has_arg:
            return
        current_graph.node(node_id, label)
        if parent is not None:
            parent_id = parent.current_node_id if hasattr(parent, 'current_node_id') else str(id(parent))
            if (parent_id, node_id) not in edges_set:
                current_graph.edge(parent_id, node_id)
                edges_set.add((parent_id, node_id))
        return
        
    if isinstance(node, A.With):
        label = "With Statement"
        # 创建 With 语句的子图
        with current_graph.subgraph(name=f"cluster_{node_id}_with") as c:
            c.attr(style='solid', penwidth='2', color='purple', label='With Block')
            prev_child = None
            # 处理 with 语句中的 items
            for item in node.items:
                item_id = f"{prefix}|{id(item)}"
                item_label = f"WithItem: {get_label(item.context_expr)}"
                if item.optional_vars:
                    item_label += f" as {get_label(item.optional_vars)}"
                c.node(item_id, item_label)
                if prev_child is None:
                    prev_child = item
                    if (node_id, item_id) not in edges_set:
                        c.edge(node_id, item_id, label="WithItem")
                        edges_set.add((node_id, item_id))
                else:
                    prev_child_id = prev_child.current_node_id if hasattr(prev_child, 'current_node_id') else str(id(prev_child))
                    if (prev_child_id, item_id) not in edges_set:
                        c.edge(prev_child_id, item_id, label="Next_Item")
                        edges_set.add((prev_child_id, item_id))
            prev_child = None
            # 处理 with 语句的 body
            for index, child in enumerate(node.body):
                child_id = f"{prefix}|{id(child)}"
                child.current_node_id = child_id
                
                # 判断是否是最后一个子节点，是否需要连接 upper_connect_node
                if index == len(node.body) - 1:
                    next_child = upper_connect_node
                    if upper_connect_node is not None and not isinstance(child, (A.FunctionDef, A.ClassDef, A.If, A.For, A.While, A.Try, A.With, A.Match)):
                        upper_id = upper_connect_node.current_node_id if hasattr(upper_connect_node, 'current_node_id') else str(id(upper_connect_node))
                        if (child_id, upper_id) not in edges_set:
                            dot.edge(child_id, upper_id, label="Next_Step")
                            edges_set.add((child_id, upper_id))
                else:
                    next_child = node.body[index + 1]
                    next_child_id = f"{prefix}|{id(next_child)}"
                    next_child.current_node_id = next_child_id

                if isinstance(child, (A.FunctionDef, A.ClassDef, A.If, A.For, A.While, A.Try, A.With, A.Match)):
                    with c.subgraph(name=f"cluster_{child_id}") as sc:
                        sc.attr(style='solid', penwidth='2', color='lightcyan')  # 区分子图样式
                        
                        if prev_child is None:
                            prev_child = child
                            if (node_id, child_id) not in edges_set:
                                dot.edge(node_id, child_id)
                                edges_set.add((node_id, child_id))
                            add_nodes_edges(child, node, edges_set, loop_stack, 
                                            prefix, sc, unfold_times, next_child,
                                            end_function_list, potential_module_map)
                        else:
                            add_nodes_edges(child, prev_child, edges_set, loop_stack,
                                            prefix, sc, unfold_times, next_child,
                                            end_function_list, potential_module_map)
                            prev_child = child
                else:
                    if prev_child is None:
                        prev_child = child
                        if (node_id, child_id) not in edges_set:
                            dot.edge(node_id, child_id)
                            edges_set.add((node_id, child_id))
                        add_nodes_edges(child, node, edges_set, loop_stack,
                                        prefix, c, unfold_times, next_child,
                                        end_function_list, potential_module_map)
                    else:
                        add_nodes_edges(child, prev_child, edges_set, loop_stack,
                                        prefix, c, unfold_times, next_child,
                                        end_function_list, potential_module_map)
                        prev_child = child
        child_iter_needs = False
        
    if isinstance(node, A.If):
        condition = get_label(node.test)  
        label += f"\nCondition: {condition}"
        node.test.current_node_id = f"{prefix}|{id(node.test)}"
        for child in A.iter_child_nodes(node.test):
            if not isinstance(child, A.Name):
                add_nodes_edges(node.test, node, edges_set, loop_stack, 
                                prefix, current_graph, unfold_times, None, 
                                end_function_list, potential_module_map)
                if (node.test.current_node_id, node_id) not in edges_set:
                    current_graph.edge(node_id, node.test.current_node_id, label="Condition")
                    edges_set.add((node_id, node.test.current_node_id))
                    break
        with current_graph.subgraph(name=f"cluster_{node_id}_true") as c:
            c.attr(style='solid', penwidth='2', color='darkgreen', label='True Branch')
            prev_child = None
            for index, child in enumerate(node.body):
                child_id = f"{prefix}|{id(child)}"
                child.current_node_id = child_id
                
                if index == len(node.body) - 1:
                    next_child = upper_connect_node
                    if upper_connect_node is not None and not isinstance(child, (A.FunctionDef, A.ClassDef, A.If, A.For, A.While, A.Try, A.With, A.Match)):
                        upper_id = upper_connect_node.current_node_id if hasattr(upper_connect_node, 'current_node_id') else str(id(upper_connect_node))
                        edge_label = "Next_Step"
                        if (child_id, upper_id) not in edges_set:
                            dot.edge(child_id, upper_id, label=edge_label)
                            edges_set.add((child_id, upper_id))
                else:
                    next_child = node.body[index + 1]
                    next_child_id = f"{prefix}|{id(next_child)}"
                    next_child.current_node_id = next_child_id
                
                if isinstance(child, (A.FunctionDef, A.ClassDef, A.If, A.For, A.While, A.Try, A.With, A.Match)):
                    with c.subgraph(name=f"cluster_{child_id}") as sc:
                        sc.attr(style='solid', penwidth='2', color='lightblue', label="")  # 区分子图样式
                        if prev_child is None:
                            prev_child = child
                            if (node_id, child_id) not in edges_set:
                                dot.edge(node_id, child_id, label="True")
                                edges_set.add((node_id, child_id))
                            add_nodes_edges(child, node, edges_set, loop_stack,
                                            prefix, sc, unfold_times, next_child,
                                            end_function_list, potential_module_map)
                        else:
                            add_nodes_edges(child, prev_child, edges_set, loop_stack,
                                            prefix, sc, unfold_times, next_child,
                                            end_function_list, potential_module_map)
                            prev_child = child
                else:
                    if prev_child is None:
                        prev_child = child
                        if (node_id, child_id) not in edges_set:
                            dot.edge(node_id, child_id, label="True")
                            edges_set.add((node_id, child_id))
                        add_nodes_edges(child, node, edges_set, loop_stack,
                                        prefix, c, unfold_times, next_child,
                                        end_function_list, potential_module_map)
                    else:
                        add_nodes_edges(child, prev_child, edges_set, loop_stack,
                                        prefix, c, unfold_times, next_child,
                                        end_function_list, potential_module_map)
                        prev_child = child

        # False 分支处理类似 True 分支，仅 label 改为 "False"
        with current_graph.subgraph(name=f"cluster_{node_id}_false") as c:
            c.attr(style='solid', penwidth='2', color='coral', label='False Branch')
            prev_child = None
            for index, child in enumerate(node.orelse):
                child_id = f"{prefix}|{id(child)}"
                child.current_node_id = child_id
                
                if index == len(node.orelse) - 1:
                    next_child = upper_connect_node
                    if upper_connect_node is not None and not isinstance(child, (A.FunctionDef, A.ClassDef, A.If, A.For, A.While, A.Try, A.With, A.Match)):
                        upper_id = upper_connect_node.current_node_id if hasattr(upper_connect_node, 'current_node_id') else str(id(upper_connect_node))
                        edge_label = "Next_Step"
                        if (child_id, upper_id) not in edges_set:
                            dot.edge(child_id, upper_id, label=edge_label)
                            edges_set.add((child_id, upper_id))
                else:
                    next_child = node.orelse[index + 1]
                    next_child_id = f"{prefix}|{id(next_child)}"
                    next_child.current_node_id = next_child_id
                
                if isinstance(child, (A.FunctionDef, A.ClassDef, A.If, A.For, A.While, A.Try, A.With, A.Match)):
                    with c.subgraph(name=f"cluster_{child_id}") as sc:
                        sc.attr(style='solid', penwidth='2', color='lightpink', label="")
                        if prev_child is None:
                            prev_child = child
                            if (node_id, child_id) not in edges_set:
                                current_graph.edge(node_id, child_id, label="False")
                                edges_set.add((node_id, child_id))
                            add_nodes_edges(child, node, edges_set, loop_stack,
                                            prefix, sc, unfold_times, next_child,
                                            end_function_list, potential_module_map)
                        else:
                            add_nodes_edges(child, prev_child, edges_set, loop_stack,
                                            prefix, sc, unfold_times, next_child,
                                            end_function_list, potential_module_map)
                            prev_child = child
                else:
                    if prev_child is None:
                        prev_child = child
                        if (node_id, child_id) not in edges_set:
                            current_graph.edge(node_id, child_id, label="False")
                            edges_set.add((node_id, child_id))
                        add_nodes_edges(child, node, edges_set, loop_stack,
                                        prefix, c, unfold_times, next_child,
                                        end_function_list, potential_module_map)
                    else:
                        add_nodes_edges(child, prev_child, edges_set, loop_stack,
                                        prefix, c, unfold_times, next_child,
                                        end_function_list, potential_module_map)
                        prev_child = child
        child_iter_needs = False
        
                

    if isinstance(node, A.Assign):
        label += '\n' + get_label(node, potential_module_map)
        for child in A.iter_child_nodes(node):
            if isinstance(child, A.Call):
                add_nodes_edges(child, node, edges_set, loop_stack,
                                prefix, current_graph, unfold_times, None,
                                end_function_list, potential_module_map)
            if isinstance(child, A.Compare):
                add_nodes_edges(child, node, edges_set, loop_stack,
                                prefix, current_graph, unfold_times, None,
                                end_function_list, potential_module_map)
        child_iter_needs = False

    if isinstance(node, A.Call):
        if unfold_times:
            unfold_times -= 1
            func = get_label(node.func)
            
            if isinstance(node.func, A.Name):
                #受限于水平暂不支持展开通过from import 直接引入的函数
                func_name = node.func.id
                full_path = get_attribute_fullpath(node.func, potential_module_map).split(".")
                #print(full_path)
                label += "\n" + get_label(node, potential_module_map)
                if func_name not in end_function_list:
                    func_def_tree = get_module_func_ast_by_name("__main__", func_name)
                    if func_def_tree:
                        func_def_node = next(A.iter_child_nodes(func_def_tree))
                        # 传递prefix为当前节点ID，确保子节点唯一
                        add_nodes_edges(func_def_node, node, edges_set, loop_stack,
                                        node_id, current_graph, unfold_times, None, 
                                        end_function_list, potential_module_map)
            elif isinstance(node.func, A.Attribute):
                func_name = node.func.attr
                full_path = get_attribute_fullpath(node.func, potential_module_map).split(".")
                label += "\n" + get_label(node, potential_module_map)
                if func_name not in end_function_list:
                    if len(full_path) == 3 and full_path[0] != "self":
                        func_def_tree = get_module_class_func_ast_by_name(full_path[0], full_path[1], func_name)
                        try: 
                            mod = importlib.import_module(full_path[0])
                            fuc_class = getattr(mod, full_path[1])
                            class_stack.append(fuc_class)
                            func_obj = getattr(fuc_class, func_name)
                            if not callable(func_obj): 
                                print(f"{func_name} is not a callable function")
                            new_module_map = get_namespace(func_obj)
                            if func_def_tree:
                                func_def_node = next(A.iter_child_nodes(func_def_tree))
                                # 传递prefix为当前节点ID，确保子节点唯一
                                add_nodes_edges(func_def_node, node, edges_set, loop_stack,
                                                node_id, current_graph, unfold_times, None, 
                                                end_function_list, new_module_map)
                            class_stack.pop()
                        except:
                            print(f"Module {full_path[0]} not found")
                        
                    elif len(full_path) == 2 and full_path[0] != "self":
                        new_module_map = potential_module_map
                        mod = None
                        func_def_tree = None
                        for mod_name in potential_module_map:
                            try:
                                mod = importlib.import_module(mod_name)
                            except:
                                continue
                            if hasattr(mod, func_name):
                                func_def_tree = get_module_func_ast_by_name(full_path[0], func_name)
                                func_obj = getattr(mod, func_name)
                                if callable(func_obj):
                                    new_module_map = get_namespace(func_obj)
                                    break
                                else:
                                    print("{} is not callable".format(func_name))
                                

                            if hasattr(mod, full_path[0]):
                                func_class = getattr(mod, full_path[0])
                                if hasattr(func_class, func_name):
                                    func_def_tree = get_module_class_func_ast_by_name(full_path[0], full_path[1], func_name)
                                    func_obj = getattr(func_class, func_name)
                                    if callable(func_obj):
                                        new_module_map = get_namespace(func_obj)
                                        break
                                    else:
                                        print("{} is not callable".format(func_name))

                        if func_def_tree:
                            func_def_node = next(A.iter_child_nodes(func_def_tree))
                            # 传递prefix为当前节点ID，确保子节点唯一
                            add_nodes_edges(func_def_node, node, edges_set, loop_stack,
                                            node_id, current_graph, unfold_times, None, 
                                            end_function_list, new_module_map)
                    elif len(full_path) == 2 and full_path[0] == "self":
                        class_obj = class_stack[-1]
                        func_obj = getattr(class_obj, func_name)
                        if callable(func_obj):
                            new_module_map = get_namespace(func_obj)
                        else:
                            print("{} is not callable".format(func_name)) 
                        tree = dot_source_prepare(func_obj)
                        if tree:
                            func_def_node = next(A.iter_child_nodes(tree))
                            # 传递prefix为当前节点ID，确保子节点唯一
                            add_nodes_edges(func_def_node, node, edges_set, loop_stack,
                                            node_id, current_graph, unfold_times, None, 
                                            end_function_list, new_module_map)

            else:
                #理论上用不到这块
                func_name = get_label(node.func) 
                label += "\n" + get_label(node, potential_module_map)
                if func_name not in end_function_list:
                    func_def_tree = get_func_ast_by_name(func_name)
                    if func_def_tree:
                        func_def_node = next(A.iter_child_nodes(func_def_tree))
                        # 传递prefix为当前节点ID，确保子节点唯一
                        add_nodes_edges(func_def_node, node, edges_set, loop_stack,
                                        node_id, current_graph, unfold_times, None,
                                        end_function_list, potential_module_map)
            child_iter_needs = False
        else:
            label += "\n" + get_label(node,potential_module_map)
            child_iter_needs = False
        

    if isinstance(node, A.BinOp):
        label = get_label(node, potential_module_map)
        for child in A.iter_child_nodes(node):
            if isinstance(child, A.Call):
                add_nodes_edges(child, node, edges_set, loop_stack,
                                prefix, current_graph, unfold_times, upper_connect_node,
                                end_function_list, potential_module_map)
        child_iter_needs = False
        
    if isinstance(node, A.UnaryOp):
        label = get_label(node, potential_module_map)
        for child in A.iter_child_nodes(node):
            if isinstance(child, A.Call):
                add_nodes_edges(child, node, edges_set, loop_stack,
                                prefix, current_graph, unfold_times, upper_connect_node,
                                end_function_list, potential_module_map)
        child_iter_needs = False
    
    if isinstance(node, A.BoolOp):
        label = get_label(node, potential_module_map)
        for child in A.iter_child_nodes(node):
            if isinstance(child, A.Compare):
                add_nodes_edges(child, node, edges_set, loop_stack,
                                prefix, current_graph, unfold_times, upper_connect_node,
                                end_function_list, potential_module_map)
            if isinstance(child, A.Call):
                add_nodes_edges(child, node, edges_set, loop_stack,
                                prefix, current_graph, unfold_times, upper_connect_node,
                                end_function_list, potential_module_map)    
        child_iter_needs = False

    if isinstance(node, A.Compare):
        label = get_label(node, potential_module_map)
        for child in A.iter_child_nodes(node):
            if isinstance(child, A.Call):
                add_nodes_edges(child, node, edges_set, loop_stack,
                                prefix, current_graph, unfold_times, upper_connect_node,
                                end_function_list, potential_module_map)
            if isinstance(child, A.Compare):
                add_nodes_edges(child, node, edges_set, loop_stack,
                                prefix, current_graph, unfold_times, upper_connect_node,
                                end_function_list, potential_module_map)
        child_iter_needs = False

    # 处理 For 循环
    if isinstance(node, A.For):
        target = get_label(node.target)
        iter_expr = get_label(node.iter)
        label += f"\nFor: {target} in {iter_expr}"
        node.upper_connect_node = upper_connect_node
        loop_stack.append(node)
        # 创建循环体子图
        with current_graph.subgraph(name=f"cluster_{node_id}_body") as c:
            c.attr(style='solid', penwidth='2', color='darkblue', label='Loop Body')
            prev_child = None
            for index, child in enumerate(node.body):
                child_id = f"{prefix}|{id(child)}"
                child.current_node_id = child_id

                if index == len(node.body) - 1:
                    next_child = upper_connect_node
                    if upper_connect_node is not None and not isinstance(child, (A.FunctionDef, A.ClassDef, A.If, A.For, A.While, A.Try, A.With, A.Match)):
                        upper_id = upper_connect_node.current_node_id if hasattr(upper_connect_node, 'current_node_id') else str(id(upper_connect_node))
                        if (child_id, upper_id) not in edges_set:
                            dot.edge(child_id, upper_id, label="Next_Step")
                            edges_set.add((child_id, upper_id))
                else:
                    next_child = node.body[index + 1]
                    next_child_id = f"{prefix}|{id(next_child)}"
                    next_child.current_node_id = next_child_id

                if isinstance(child, (A.FunctionDef, A.ClassDef, A.If, A.For, A.While, A.Try, A.With, A.Match)):
                    with c.subgraph(name=f"cluster_{child_id}") as sc:
                        sc.attr(style='solid', penwidth='2', color='lightblue', label="")
                        if prev_child is None:
                            prev_child = child
                            if (node_id, child_id) not in edges_set:
                                dot.edge(node_id, child_id)
                                edges_set.add((node_id, child_id))
                            add_nodes_edges(child, node, edges_set, loop_stack,
                                            prefix, sc, unfold_times, next_child,
                                            end_function_list, potential_module_map)
                        else:
                            add_nodes_edges(child, prev_child, edges_set, loop_stack,
                                            prefix, sc, unfold_times, next_child,
                                            end_function_list, potential_module_map)
                            prev_child = child
                else:
                    if prev_child is None:
                        prev_child = child
                        if (node_id, child_id) not in edges_set:
                            dot.edge(node_id, child_id)
                            edges_set.add((node_id, child_id))
                        add_nodes_edges(child, node, edges_set, loop_stack,
                                        prefix, c, unfold_times, next_child,
                                        end_function_list, potential_module_map)
                    else:
                        add_nodes_edges(child, prev_child, edges_set, loop_stack,
                                        prefix, c, unfold_times, next_child,
                                        end_function_list, potential_module_map)
                        prev_child = child
            # 处理 orelse（如果有）
            if node.orelse:
                with current_graph.subgraph(name=f"cluster_{node_id}_orelse") as c:
                    c.attr(style='solid', penwidth='2', color='darkyellow', label='Else')
                    prev_child = None
                    for index, child in enumerate(node.orelse):
                        child_id = f"{prefix}|{id(child)}"
                        child.current_node_id = child_id

                        if index == len(node.orelse) - 1:
                            next_child = upper_connect_node
                            if upper_connect_node is not None and not isinstance(child, (A.FunctionDef, A.ClassDef, A.If, A.For, A.While, A.Try, A.With, A.Match)):
                                upper_id = upper_connect_node.current_node_id if hasattr(upper_connect_node, 'current_node_id') else str(id(upper_connect_node))
                                if (child_id, upper_id) not in edges_set:
                                    dot.edge(child_id, upper_id, label="Next_Step")
                                    edges_set.add((child_id, upper_id))
                        else:
                            next_child = node.orelse[index + 1]
                            next_child_id = f"{prefix}|{id(next_child)}"
                            next_child.current_node_id = next_child_id
                        if isinstance(child, (A.FunctionDef, A.ClassDef, A.If, A.For, A.While, A.Try, A.With, A.Match)):
                            with c.subgraph(name=f"cluster_{child_id}") as sc:
                                sc.attr(style='solid', penwidth='2', color='lightpink', label="")
                                if prev_child is None:
                                    prev_child = child
                                    if (node_id, child_id) not in edges_set:
                                        dot.edge(node_id, child_id)
                                        edges_set.add((node_id, child_id))
                                        add_nodes_edges(child, node, edges_set, loop_stack,
                                                        prefix, sc, unfold_times, next_child,
                                                        end_function_list, potential_module_map)
                                else:
                                    add_nodes_edges(child, prev_child, edges_set, loop_stack,
                                                    prefix, sc, unfold_times, next_child,
                                                    end_function_list, potential_module_map)
                                    prev_child = child
                        else:
                            if prev_child is None:
                                prev_child = child
                                if (node_id, child_id) not in edges_set:
                                    dot.edge(node_id, child_id)
                                    edges_set.add((node_id, child_id))
                                    add_nodes_edges(child, node, edges_set, loop_stack,
                                                    prefix, c, unfold_times, next_child,
                                                    end_function_list, potential_module_map)
                            else:
                                add_nodes_edges(child, prev_child, edges_set, loop_stack,
                                                prefix, c, unfold_times, next_child,
                                                end_function_list, potential_module_map)
                                prev_child = child
        loop_stack.pop()
        child_iter_needs = False

    # 处理 While 循环
    if isinstance(node, A.While):
        condition = get_label(node.test)
        label += f"\nWhile: {condition}"
        node.upper_connect_node = upper_connect_node
        loop_stack.append(node)
        with current_graph.subgraph(name=f"cluster_{node_id}_While_body") as c:
            c.attr(style='solid', penwidth='2', color='pink', label='Loop Body')
            prev_child = None

            for index, child in enumerate(node.body):
                child_id = f"{prefix}|{id(child)}"
                child.current_node_id = child_id

                if index == len(node.body) - 1:
                    next_child = upper_connect_node
                    if upper_connect_node is not None and not isinstance(child, (A.FunctionDef, A.ClassDef, A.If, A.For, A.While, A.Try, A.With, A.Match)):
                        upper_id = upper_connect_node.current_node_id if hasattr(upper_connect_node, 'current_node_id') else str(id(upper_connect_node))
                        if (child_id, upper_id) not in edges_set:
                            dot.edge(child_id, upper_id, label="Next_Step")
                            edges_set.add((child_id, upper_id))
                else:
                    next_child = node.body[index + 1]
                    next_child_id = f"{prefix}|{id(next_child)}"
                    next_child.current_node_id = next_child_id
                if isinstance(child, (A.FunctionDef, A.ClassDef, A.If, A.For, A.While, A.Try, A.With, A.Match)):
                    with c.subgraph(name=f"cluster_{child_id}") as sc:
                        sc.attr(style='solid', penwidth='2', color='lightblue', label="")
                        if prev_child is None:
                            prev_child = child
                            if (node_id, child_id) not in edges_set:
                                dot.edge(node_id, child_id)
                                edges_set.add((node_id, child_id))
                            add_nodes_edges(child, node, edges_set, loop_stack,
                                            prefix, sc, unfold_times, next_child,
                                            end_function_list, potential_module_map)
                        else:
                            add_nodes_edges(child, prev_child, edges_set, loop_stack,
                                            prefix, sc, unfold_times, next_child,
                                            end_function_list, potential_module_map)
                            prev_child = child
                else:
                    if prev_child is None:
                        prev_child = child
                        if (node_id, child_id) not in edges_set:
                            dot.edge(node_id, child_id)
                            edges_set.add((node_id, child_id))
                        add_nodes_edges(child, node, edges_set, loop_stack,
                                        prefix, c, unfold_times, next_child,
                                        end_function_list, potential_module_map)
                    else:
                        add_nodes_edges(child, prev_child, edges_set, loop_stack,
                                        prefix, c, unfold_times, next_child,
                                        end_function_list, potential_module_map)
                        prev_child = child

            # 处理 orelse 分支
            if node.orelse:
                with current_graph.subgraph(name=f"cluster_{node_id}_orelse") as c:
                    c.attr(style='solid', penwidth='2', color='darkgrey', label='Else')
                    prev_orelse = None
                    for index, child in enumerate(node.orelse):
                        child_id = f"{prefix}|{id(child)}"
                        child.current_node_id = child_id

                        if index == len(node.orelse) - 1:
                            next_child = upper_connect_node
                            if upper_connect_node is not None and not isinstance(child, (A.FunctionDef, A.ClassDef, A.If, A.For, A.While, A.Try, A.With, A.Match)):
                                upper_id = upper_connect_node.current_node_id if hasattr(upper_connect_node, 'current_node_id') else str(id(upper_connect_node))
                                if (child_id, upper_id) not in edges_set:
                                    dot.edge(child_id, upper_id, label="Next_Step")
                                    edges_set.add((child_id, upper_id))

                        else:
                            next_child = node.orelse[index + 1]
                            next_child_id = f"{prefix}|{id(next_child)}"
                            next_child.current_node_id = next_child_id
                        if isinstance(child, (A.FunctionDef, A.ClassDef, A.If, A.For, A.While, A.Try, A.With, A.Match)):
                            with c.subgraph(name=f"cluster_{child_id}") as sc:
                                sc.attr(style='solid', penwidth='2', color='lightpink', label="")
                                if prev_orelse is None:
                                    prev_orelse = child
                                    if (node_id, child_id) not in edges_set:
                                        dot.edge(node_id, child_id)
                                        edges_set.add((node_id, child_id))
                                    add_nodes_edges(child, node, edges_set, loop_stack,
                                                    prefix, sc, unfold_times, next_child,
                                                    end_function_list, potential_module_map)
                                else:
                                    add_nodes_edges(child, prev_orelse, edges_set, loop_stack,
                                                     prefix, sc, unfold_times, next_child,
                                                     end_function_list, potential_module_map)
                                    prev_orelse = child
                        else:
                            if prev_orelse is None:
                                prev_orelse = child
                                if (node_id, child_id) not in edges_set:
                                    dot.edge(node_id, child_id)
                                    edges_set.add((node_id, child_id))
                                add_nodes_edges(child, node, edges_set, loop_stack,
                                                prefix, c, unfold_times, next_child,
                                                end_function_list, potential_module_map)
                            else:
                                add_nodes_edges(child, prev_orelse, edges_set, loop_stack,
                                                prefix, c, unfold_times, next_child,
                                                end_function_list, potential_module_map)
                                prev_orelse = child
        loop_stack.pop()
        child_iter_needs = False

    #  处理 Match 匹配
    if isinstance(node, A.Match):
        label = f"Match: {get_label(node.subject)}"
        for case in node.cases:
            case_id = f"{prefix}|{id(case)}"
            case_label = f"Case: {get_label(case.pattern)}"
            if case.guard:
                case_label += f" if {get_label(case.guard)}"
            current_graph.node(case_id, case_label)
            current_graph.edge(node_id, case_id)
            edges_set.add((node_id, case_id))
            case.current_node_id = case_id
            prev_child = None
            for index, child in enumerate(case.body):
                child_id = f"{prefix}|{id(child)}"
                child.current_node_id = child_id

                if index == len(case.body) - 1:
                    next_child = upper_connect_node
                    if upper_connect_node is not None and not isinstance(child, (A.FunctionDef, A.ClassDef, A.If, A.For, A.While, A.Try, A.With, A.Match)):
                        upper_id = upper_connect_node.current_node_id if hasattr(upper_connect_node, 'current_node_id') else str(id(upper_connect_node))
                        if (child_id, upper_id) not in edges_set:
                            dot.edge(child_id, upper_id, label="Next_Step")
                            edges_set.add((child_id, upper_id))

                else:
                    next_child = case.body[index + 1]
                    next_child_id = f"{prefix}|{id(next_child)}"
                    next_child.current_node_id = next_child_id
                if isinstance(child, (A.FunctionDef, A.ClassDef, A.If, A.For, A.While, A.Try, A.With, A.Match)):
                    with current_graph.subgraph(name=f"cluster_{child_id}") as c:
                        c.attr(style='solid', penwidth='2', color='lightcyan', label="")

                        if prev_child is None:
                            prev_child = child
                            if (case_id, child_id) not in edges_set:
                                dot.edge(case_id, child_id)
                                edges_set.add((case_id, child_id))
                            add_nodes_edges(child, case, edges_set, loop_stack,
                                            prefix, c, unfold_times, next_child,
                                            end_function_list, potential_module_map)
                        else:
                            add_nodes_edges(child, prev_child, edges_set, loop_stack,
                                            prefix, c, unfold_times, next_child,
                                            end_function_list, potential_module_map)
                            prev_child = child
                else:
                    if prev_child is None:
                        prev_child = child
                        if (case_id, child_id) not in edges_set:
                            dot.edge(case_id, child_id)
                            edges_set.add((case_id, child_id))
                        add_nodes_edges(child, case, edges_set, loop_stack,
                                        prefix, current_graph, unfold_times, next_child,
                                        end_function_list, potential_module_map)
                    else:
                        add_nodes_edges(child, prev_child, edges_set, loop_stack,
                                        prefix, current_graph, unfold_times, next_child,
                                        end_function_list, potential_module_map)
                        prev_child = child
        child_iter_needs = False
        
    if isinstance(node, A.MatchValue):
        label = get_label(node, potential_module_map)
    if isinstance(node, A.MatchSequence):
        label = get_label(node, potential_module_map)
    if isinstance(node, A.MatchMapping):
        label = get_label(node, potential_module_map)
    if isinstance(node, A.MatchClass):
        label = get_label(node, potential_module_map)
    if isinstance(node, A.MatchStar):
        label = get_label(node, potential_module_map)
    if isinstance(node, A.MatchAs):
        label = get_label(node, potential_module_map)
    if isinstance(node, A.MatchOr):
        label = get_label(node, potential_module_map)

    # 在 add_nodes_edges 函数中增加对 A.Try 的处理
    if isinstance(node, A.Try):
        # 主 Try 块样式
        with current_graph.subgraph(name=f"cluster_{node_id}_try") as c:
            c.attr(style='solid', penwidth='2', color='darkgoldenrod', label='Try Block')
            prev_child = None
            # 处理 try body
            for index, child in enumerate(node.body):
                child_id = f"{prefix}|{id(child)}"
                child.current_node_id = child_id
                
                if index == len(node.body) - 1:
                    next_child = upper_connect_node
                    if upper_connect_node is not None and not isinstance(child, (A.FunctionDef, A.ClassDef, A.If, A.For, A.While, A.Try, A.With, A.Match)):
                        upper_id = upper_connect_node.current_node_id if hasattr(upper_connect_node, 'current_node_id') else str(id(upper_connect_node))
                        if (child_id, upper_id) not in edges_set:
                            dot.edge(child_id, upper_id, label="Next_Step")
                            edges_set.add((child_id, upper_id))

                else:
                    next_child = node.body[index + 1]
                    next_child_id = f"{prefix}|{id(next_child)}"
                    next_child.current_node_id = next_child_id
                if isinstance(child, (A.FunctionDef, A.ClassDef, A.If, A.For, A.While, A.Try, A.With, A.Match)):
                    with c.subgraph(name=f"cluster_{child_id}") as sc:
                        sc.attr(style='solid', penwidth='2', color='lightyellow')
                        if prev_child is None:
                            prev_child = child
                            if (node_id, child_id) not in edges_set:
                                dot.edge(node_id, child_id)
                                edges_set.add((node_id, child_id))
                            add_nodes_edges(child, node, edges_set, loop_stack,
                                            prefix, sc, unfold_times, next_child,
                                            end_function_list, potential_module_map)
                        else:
                            add_nodes_edges(child, prev_child, edges_set, loop_stack,
                                            prefix, sc, unfold_times, next_child,
                                            end_function_list, potential_module_map)
                            prev_child = child
                else:
                    if prev_child is None:
                        prev_child = child
                        if (node_id, child_id) not in edges_set:
                            dot.edge(node_id, child_id)
                            edges_set.add((node_id, child_id))
                        add_nodes_edges(child, node, edges_set, loop_stack,
                                        prefix, c, unfold_times, next_child,
                                        end_function_list, potential_module_map)
                    else:
                        add_nodes_edges(child, prev_child, edges_set, loop_stack,
                                        prefix, c, unfold_times, next_child,
                                        end_function_list, potential_module_map)
                        prev_child = child

        # 处理 Exception Handlers
        for handler_index, handler in enumerate(node.handlers):
            handler_id = f"{prefix}|{id(handler)}"
            handler_type = get_label(handler.type) if handler.type else "All Exceptions"
            with current_graph.subgraph(name=f"cluster_{handler_id}_except") as c:
                c.attr(style='solid', penwidth='2', color='red', label=f'Except {handler_type}')
                prev_child = None
                # 连接前一个 handler 或 try 块
                prev_handler = node.handlers[handler_index-1] if handler_index > 0 else node
                prev_id = prev_handler.current_node_id if hasattr(prev_handler, 'current_node_id') else str(id(prev_handler))
                if (prev_id, handler_id) not in edges_set:
                    dot.edge(prev_id, handler_id, label="Exception")
                    edges_set.add((prev_id, handler_id))
                    
                # 处理 handler body
                for index, child in enumerate(handler.body):
                    child_id = f"{prefix}|{id(child)}"
                    child.current_node_id = child_id
                    
                    if index == len(handler.body) - 1:
                        next_child = upper_connect_node
                    else:
                        next_child = handler.body[index + 1]
                    if isinstance(child, (A.FunctionDef, A.ClassDef, A.If, A.For, A.While, A.Try, A.With, A.Match)):
                        with c.subgraph(name=f"cluster_{child_id}") as sc:
                            sc.attr(style='solid', penwidth='2', color='lightcoral')
                            if prev_child is None:
                                prev_child = child
                                if (handler_id, child_id) not in edges_set:
                                    dot.edge(handler_id, child_id)
                                    edges_set.add((handler_id, child_id))
                                add_nodes_edges(child, handler, edges_set, loop_stack,
                                                prefix, sc, unfold_times, next_child,
                                                end_function_list, potential_module_map)
                            else:
                                add_nodes_edges(child, prev_child, edges_set, loop_stack,
                                                prefix, sc, unfold_times, next_child,
                                                end_function_list, potential_module_map)
                                prev_child = child
                    else:
                        if prev_child is None:
                            prev_child = child
                            if (handler_id, child_id) not in edges_set:
                                dot.edge(handler_id, child_id)
                                edges_set.add((handler_id, child_id))
                            add_nodes_edges(child, handler, edges_set, loop_stack,
                                            prefix, c, unfold_times, next_child,
                                            end_function_list, potential_module_map)
                        else:
                            add_nodes_edges(child, prev_child, edges_set, loop_stack,
                                            prefix, c, unfold_times, next_child,
                                            end_function_list, potential_module_map)
                            prev_child = child

        # 处理 Else 块
        if node.orelse:
            with current_graph.subgraph(name=f"cluster_{node_id}_else") as c:
                c.attr(style='solid', penwidth='2', color='darkgreen', label='Else Block')
                prev_child = None
                for index, child in enumerate(node.orelse):
                    child_id = f"{prefix}|{id(child)}"
                    child.current_node_id = child_id
                    
                    if index == len(node.orelse) - 1:
                        next_child = upper_connect_node
                        if upper_connect_node is not None and not isinstance(child, (A.FunctionDef, A.ClassDef, A.If, A.For, A.While, A.Try, A.With, A.Match)):
                            upper_id = upper_connect_node.current_node_id if hasattr(upper_connect_node, 'current_node_id') else str(id(upper_connect_node))
                            if (child_id, upper_id) not in edges_set:
                                dot.edge(child_id, upper_id, label="Next_Step")
                                edges_set.add((child_id, upper_id))
                    else:
                        next_child = node.orelse[index + 1]
                        next_child_id = f"{prefix}|{id(next_child)}"
                        next_child.current_node_id = next_child_id
                    if isinstance(child, (A.FunctionDef, A.ClassDef, A.If, A.For, A.While, A.Try, A.With, A.Match)):
                        with c.subgraph(name=f"cluster_{child_id}") as sc:
                            sc.attr(style='solid', penwidth='2', color='lightgreen')
                            if prev_child is None:
                                prev_child = child
                                if (node_id, child_id) not in edges_set:
                                    dot.edge(node_id, child_id)
                                    edges_set.add((node_id, child_id))
                                add_nodes_edges(child, node, edges_set, loop_stack,
                                                prefix, sc, unfold_times, next_child,
                                                end_function_list, potential_module_map)
                            else:
                                add_nodes_edges(child, prev_child, edges_set, loop_stack,
                                                prefix, sc, unfold_times, next_child,
                                                end_function_list, potential_module_map)
                                prev_child = child
                    else:
                        if prev_child is None:
                            prev_child = child
                            if (node_id, child_id) not in edges_set:
                                dot.edge(node_id, child_id)
                                edges_set.add((node_id, child_id))
                            add_nodes_edges(child, node, edges_set, loop_stack,
                                            prefix, c, unfold_times, next_child,
                                            end_function_list, potential_module_map)
                        else:
                            add_nodes_edges(child, prev_child, edges_set, loop_stack,
                                            prefix, c, unfold_times, next_child,
                                            end_function_list, potential_module_map)
                            prev_child = child
        # 处理 Finally 块
        if node.finalbody:
            with current_graph.subgraph(name=f"cluster_{node_id}_finally") as c:
                c.attr(style='solid', penwidth='2', color='brown', label='Finally Block')
                prev_child = None
                for index, child in enumerate(node.finalbody):
                    child_id = f"{prefix}|{id(child)}"
                    child.current_node_id = child_id
                    
                    if index == len(node.finalbody) - 1:
                        next_child = upper_connect_node
                        if upper_connect_node is not None and not isinstance(child, (A.FunctionDef, A.ClassDef, A.If, A.For, A.While, A.Try, A.With, A.Match)):
                            upper_id = upper_connect_node.current_node_id if hasattr(upper_connect_node, 'current_node_id') else str(id(upper_connect_node))
                            if(child_id, upper_id) not in edges_set:
                                dot.edge(child_id, upper_id, label="Next_Step")
                                edges_set.add((child_id, upper_id))
                    else:
                        next_child = node.finalbody[index + 1]
                        next_child_id = f"{prefix}|{id(next_child)}"
                        next_child.current_node_id = next_child_id
                    if isinstance(child, (A.FunctionDef, A.ClassDef, A.If, A.For, A.While, A.Try, A.With, A.Match)):
                        with c.subgraph(name=f"cluster_{child_id}") as sc:
                            sc.attr(style='solid', penwidth='2', color='peachpuff')
                            if prev_child is None:
                                prev_child = child
                                if (node_id, child_id) not in edges_set:
                                    dot.edge(node_id, child_id)
                                    edges_set.add((node_id, child_id))
                                add_nodes_edges(child, node, edges_set, loop_stack, 
                                                prefix, sc, unfold_times, next_child,
                                                end_function_list, potential_module_map)
                            else:
                                add_nodes_edges(child, prev_child, edges_set, loop_stack, 
                                                prefix, sc, unfold_times, next_child,
                                                end_function_list, potential_module_map)
                                prev_child = child
                    else:
                        if prev_child is None:
                            prev_child = child
                            if (node_id, child_id) not in edges_set:
                                dot.edge(node_id, child_id)
                                edges_set.add((node_id, child_id))
                            add_nodes_edges(child, node, edges_set, loop_stack,
                                            prefix, c, unfold_times, next_child,
                                            end_function_list, potential_module_map)
                        else:
                            add_nodes_edges(child, prev_child, edges_set, loop_stack,
                                            prefix, c, unfold_times, next_child,
                                            end_function_list, potential_module_map)
                            prev_child = child
        
        child_iter_needs = False
     # 处理 Break 节点
    if isinstance(node, A.Break):
        if loop_stack:
            target_node = loop_stack[-1].upper_connect_node  # 假设 upper_connect_node 已保存
            target_id = f"{prefix}|{id(target_node)}"
            node_id = f"{prefix}|{id(node)}"
            
            if (node_id, target_id) not in edges_set:
                dot.edge(node_id, target_id, label="Break→", constraint="False")
                edges_set.add((node_id, target_id))
        else:
            raise ValueError("Break outside loop")
        child_iter_needs = False

    # 处理 Continue 节点
    if isinstance(node, A.Continue):
        if loop_stack:
            target_node = loop_stack[-1]  # 获取最近的循环节点
            target_id = f"{prefix}|{id(target_node)}"
            node_id = f"{prefix}|{id(node)}"
            
            if (node_id, target_id) not in edges_set:
                dot.edge(node_id, target_id, label="Continue→", constraint="False")
                edges_set.add((node_id, target_id))
        else:
            raise ValueError("Continue outside loop")
        child_iter_needs = False
    if isinstance(node, A.List):
        label += get_label(node, potential_module_map)
        child_iter_needs = False
    if isinstance(node, A.Tuple):
        label += get_label(node, potential_module_map)
        child_iter_needs = False
    if isinstance(node, A.Set):
        label += get_label(node, potential_module_map)
        child_iter_needs = False
    if isinstance(node, A.Dict):
        label += get_label(node, potential_module_map)
        child_iter_needs = False

    # 添加字段信息（排除 ctx 和空值）
    for field, value in A.iter_fields(node):
        if field == "ctx" or value is None or value == []:
            continue
        if not str(value).startswith("<ast") and not str(value).startswith("[<ast") :  # 只添加非AST字段
            label += f"\n{field}: {repr(value)}"
    
    #if not isinstance(node, A.Name):
    current_graph.node(node_id, label)

    if upper_connect_node is not None:
        if isinstance(node, (A.Expr, A.Assign, A.Return)):
            upper_connect_node_id = upper_connect_node.current_node_id if hasattr(upper_connect_node, 'current_node_id') else str(id(upper_connect_node))
            if (node_id, upper_connect_node_id) not in edges_set:
                edge_label = "Next_Step"
                dot.edge(node_id, upper_connect_node_id, label = edge_label)
                edges_set.add((node_id, upper_connect_node_id))
    # 连接父节点
    if parent is not None:
        if not isinstance(parent, (A.FunctionDef, A.ClassDef, A.If, A.For, A.While, A.Try, A.With, A.Match)):
            parent_id = parent.current_node_id if hasattr(parent, 'current_node_id') else str(id(parent))
            if (parent_id, node_id) not in edges_set:
                current_graph.edge(parent_id, node_id)
                edges_set.add((parent_id, node_id))
    
    # 递归处理子节点
    if child_iter_needs:
        for child in A.iter_child_nodes(node):
            # 跳过 Load 等无用节点
            if child.__class__.__name__ in ["Load", "Store", "Del"]:
                continue
            
            edge_label = None
            if hasattr(node, "test"):
                if child == node.test:
                    edge_label = "Condition"
            if isinstance(node, A.Expr):
                edge_label = "Expression_Is"
                
            # 优先处理带标签的边
            
            child_id = f"{prefix}|{id(child)}"
            if (node_id, child_id) not in edges_set:
                current_graph.edge(node_id, child_id, label=edge_label)
                edges_set.add((node_id, child_id))
                add_nodes_edges(child, node, edges_set, loop_stack,
                                prefix, current_graph, unfold_times, upper_connect_node,
                                end_function_list, potential_module_map)
        









def get_label(node, potential_module_map=None):
    if potential_module_map is None:
        potential_module_map = {}
    if isinstance(node, A.Compare):
        left = get_label(node.left)
        parts = []
        for op, comp in zip(node.ops, node.comparators):
            op_symbol = get_op_label(op)
            comp_expr = get_label(comp)
            parts.append(f"{op_symbol} {comp_expr}")
        return f"{left} {' '.join(parts)}"
    
    if isinstance(node, A.Assign):
        targets = ', '.join(get_label(target) for target in node.targets)
        value = get_label(node.value)
        return f"{targets} = {value}"
    
    if isinstance(node, A.BinOp):
        # 处理二元运算（如 a + b）
        left = get_label(node.left)
        op = get_op_label(node.op)
        right = get_label(node.right)
        return f"{left} {op} {right}"
    
    if isinstance(node, A.UnaryOp):
        # 处理一元运算（如 -x）
        op = get_op_label(node.op)
        operand = get_label(node.operand)
        return f"{op}{operand}"

    if isinstance(node, A.Call):
        # 处理函数调用（如 func(arg)）
        func = get_label(node.func, potential_module_map)
        args = ', '.join(get_label(arg, potential_module_map) for arg in node.args)
        return f"{func}({args})"
    
    if isinstance(node, A.Name):
        # 处理变量名
        return potential_module_map.get(node.id, node.id)
    if isinstance(node, A.BoolOp):
        # 处理布尔操作（如 a or b）
        op_symbol = ' ' + get_op_label(node.op) + ' '
        values = [get_label(value) for value in node.values]
        return f"{op_symbol.join(values)}"
    
    if isinstance(node, A.Constant):
        # 处理常量值
        return  repr(node.value)
    
    if isinstance(node, A.Attribute):
        # 处理属性访问（如 obj.attr）
        value = get_label(node.value, potential_module_map)
        return f"{value}.{node.attr}"
    
    if isinstance(node, A.For):
        target = get_label(node.target)
        iter_expr = get_label(node.iter)
        return f"For {target} in {iter_expr}"
    if isinstance(node, A.While):
        condition = get_label(node.test)
        return f"While {condition}"
    if isinstance(node, A.Match):
        subject = get_label(node.subject)
        cases = []
        for case in node.cases:
            pattern = get_label(case.pattern)
            guard = get_label(case.guard) if case.guard else None
            body = [get_label(stmt) for stmt in case.body]
            case_str = f"case {pattern}"
            if guard:
                case_str += f" if {guard}"
            case_str += ": " + "; ".join(body)
            cases.append(case_str)
        return f"match {subject}:\n  " + "\n  ".join(cases)
    if isinstance(node, A.MatchValue):
        return f"MatchValue: {get_label(node.value)}"
    if isinstance(node, A.MatchSequence):
        elements = ', '.join(get_label(element) for element in node.patterns)
        return f"MatchSequence: [{elements}]"
    if isinstance(node, A.MatchMapping):
        keys = ', '.join(get_label(key) for key in node.keys)
        values = ', '.join(get_label(value) for value in node.patterns)
        return f"MatchMapping: {{{keys}: {values}}}"
    if isinstance(node, A.MatchClass):
        class_name = get_label(node.cls)
        patterns = ', '.join(get_label(pattern) for pattern in node.patterns)
        return f"MatchClass: {class_name}({patterns})"
    if isinstance(node, A.MatchStar):
        name = get_label(node.name) if node.name else "*"
        return f"MatchStar: {name}"
    if isinstance(node, A.MatchAs):
        name = get_label(node.name) if node.name else "_"
        return f"MatchAs: {name}"
    if isinstance(node, A.MatchOr):
        patterns = ' | '.join(get_label(pattern) for pattern in node.patterns)
        return f"MatchOr: {patterns}"
    if isinstance(node, A.List):
        return '[' + ', '.join(get_label(value) for value in node.elts) + ']'
    if isinstance(node, A.Tuple):
        return '(' + ', '.join(get_label(value) for value in node.elts) + ')'
    if isinstance(node, A.Set):
        return '{' + ', '.join(get_label(value) for value in node.elts) + '}'
    if isinstance(node, A.Dict):
        items = [f"{get_label(key)}: {get_label(value)}" for key, value in zip(node.keys, node.values)]
        return '{' + ', '.join(items) + '}'
    # 添加其他需要处理的节点类型...
    else:
        # 默认返回类名
        return node.__class__.__name__


def get_op_label(op):
    """将 AST 操作符转换为符号"""
    op_type = type(op)
    return {
        A.Add: '+',
        A.Sub: '-',
        A.Mult: '*',
        A.Div: '/',
        A.Eq: '==',
        A.NotEq: '!=',
        A.Lt: '<',
        A.LtE: '<=',
        A.Gt: '>',
        A.GtE: '>=',
        A.And: 'and',
        A.Or: 'or',
        A.Not: 'not',
        A.USub: '-',  
        A.Or: 'or',
        A.In: 'in',
        A.NotIn: 'not in',
        A.Is: 'is',
        A.IsNot: 'is not',
        A.Invert: '~',
        A.BitAnd: '&',
        A.BitOr: '|',
        A.FloorDiv: '//',
        A.Mod: '%',
        A.Pow: '**',
        A.MatMult: '@',
        A.BitXor: '^',
        A.FloorDiv: '//',
        A.LShift: '<<',
        A.RShift: '>>'
        # 添加其他操作符...
    }.get(op_type, op.__class__.__name__)  # 找不到则返回类名


def build_alias_map_from_module(mod):
    """从模块对象中提取别名映射"""
    alias_map = {}
    try:
        source = inspect.getsource(mod)
        tree = A.parse(source)
        for node in A.walk(tree):
            if isinstance(node, (A.Import, A.ImportFrom)):
                for alias in node.names:
                    if alias.asname:
                        alias_map[alias.asname] = alias.name
    except Exception as e:
        print(f"Error building alias map from module {mod.__name__}: {e}")
    return alias_map


def get_namespace(func):
    mod = inspect.getmodule(func)
    current_module = mod.__name__
    namespace_map = {}  

    # 构建模块级的别名映射
    alias_map = build_alias_map_from_module(mod)

    # 遍历模块字典获取导入的模块
    for name, value in mod.__dict__.items():
        if name in ('__builtins__', '__name__', '__file__', '__package__'):
            continue

        # 处理直接导入的模块（如 import numpy as np）
        if isinstance(value, types.ModuleType):
            original_name = value.__name__
            if original_name == current_module:
                continue

            # 添加原始模块名到字典
            namespace_map[original_name] = original_name

            # 添加所有匹配的别名到字典
            for alias, real in alias_map.items():
                if real == original_name:
                    namespace_map[alias] = original_name

    # 添加 "__main__"
    namespace_map["__main__"] = "__main__"

    return namespace_map
# 输入为str
def get_func_ast_by_name(func_name):
    functions = globals()
    if func_name in functions:
        func = functions[func_name]
        if callable(func):
            source_code = inspect.getsource(func)
            func_tree=A.parse(textwrap.dedent(source_code))
            return func_tree
        else:
            print(ValueError(f"{func_name} is not callable."))
            return None
    else:
        print(ValueError(f"Function {func_name} not found."))
        return None

# 输入为str
def get_module_func_ast_by_name(module_name, func_name):
    try:
        mod = importlib.import_module(module_name)
    except ImportError:
        print(f"Module '{module_name}' not found.")
        return None
    func = getattr(mod, func_name, None)
    if func:
        try:
            source_code = inspect.getsource(func)
            func_tree=A.parse(textwrap.dedent(source_code))
            return func_tree
        except Exception as e:
            print(f"Error calling function '{func_name}' in module '{module_name}': {e}")
            return None
    else:
        print(f"Function '{func_name}' not found in module '{module_name}'.")
        return None

# 输入为str
def get_module_class_func_ast_by_name(module_name, class_name, func_name):
    try:
        mod = importlib.import_module(module_name)
    except ImportError:
        print(f"Module '{module_name}' not found.")
        return None
    func_obj = getattr(mod, class_name, None)
    if func_obj:
        func = getattr(func_obj, func_name, None)
        if func:
            try:
                source_code = inspect.getsource(func)
                func_tree=A.parse(textwrap.dedent(source_code))
                return func_tree
            except Exception as e:
                print(f"Error calling function '{func_name}' in class '{class_name}': {e}")
                return None
        else:
            print(f"Function '{func_name}' not found in class '{class_name}'.")
            return None
    else:
        print(f"Class '{class_name}' not found in module '{module_name}'.")
        return None

def get_function_from_string(func_path):
    if '.' not in func_path:
        # 处理无模块路径的情况（如 "my_func"）
        main_module = sys.modules['__main__']
        if hasattr(main_module, func_path):
            return getattr(main_module, func_path)
        else:
            print(f"Function '{func_path}' not found in __main__ module")
            return None
    
    # 分割模块/类和函数名
    module_class, func_name = func_path.rsplit('.', 1)
    
    # 分割模块和类名（支持嵌套类）
    if '.' in module_class:
        module_name, class_name = module_class.rsplit('.', 1)
    else:
        module_name = module_class
        class_name = None
    
    # 导入模块
    module = importlib.import_module(module_name)
    
    if class_name:
        # 获取类
        cls = getattr(module, class_name)
        # 从类中获取函数对象（静态方法、类方法或实例方法）
        return getattr(cls, func_name)
    else:
        # 直接从模块获取函数
        if hasattr(module, func_name):
            return getattr(module, func_name)
        else:
            print(f"Function '{func_name}' not found in module '{module_name}'")

def get_attribute_fullpath(node, potential_module_map=None):
    """
    解析 A.Attribute 节点的完整路径，并替换别名
    :param node: AST 节点
    :param potential_module_map: 别名映射表（如 {"np": "numpy", "DF": "pandas.DataFrame"}）
    :return: str
    """
    if potential_module_map is None:
        potential_module_map = {}

    if isinstance(node, A.Attribute):
        # 递归处理属性链（如 df["col"].head()）
        value = get_attribute_fullpath(node.value, potential_module_map)
        return f"{value}.{node.attr}"

    elif isinstance(node, A.Name):
        # 优先从别名映射中查找（如 np → numpy）
        if node.id in potential_module_map:
            return potential_module_map[node.id]
        # 若未找到，直接返回原始名称
        return node.id
    
def save_ast(file_path):
    """path should include file name"""
    dot.render(file_path, format='pdf', cleanup=True)
    return

def build_alias_map(tree):
    alias_map = {}

    for node in A.walk(tree):
        if isinstance(node, A.Import):
            for alias in node.names:
                if alias.asname:
                    alias_map[alias.asname] = alias.name
        elif isinstance(node, A.ImportFrom):
            module = getattr(node, 'module', None)
            if not module:
                continue  # 跳过无效模块
            for alias in node.names:
                if alias.asname:
                    alias_map[alias.asname] = f"{module}.{alias.name}"
                else:
                    full_name = f"{module}.{alias.name}"
                    alias_map[alias.name] = full_name

    return alias_map