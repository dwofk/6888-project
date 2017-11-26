# Module object

class HWError(Exception):
    pass

class Module(object):
    def __init__(self, *args, **kwargs):
        self.name = str(id(self))
        self.path = ""
        self.sub_modules = []

        self.stat_type = 'hide'
        self.raw_stats = {}
        self.final_stats = {}

        self.instantiate(*args, **kwargs)
        self.register_modules()

    def setup(self):
        pass

    def __setup__(self, path=''):
        self.setup()
        self.path = "%s/%s" % (path, self.name)
        for sub_module in self.sub_modules:
            sub_module.__setup__(self.path)

    def instantiate(self):
        raise HWError("Cannot instantiate abstract module")

    def finalize_stats(self):
        self.final_stats = { k:v for k, v in self.raw_stats.items() }
        for sub_module in self.sub_modules:
            sub_module.finalize_stats()
            if sub_module.stat_type == 'aggregate':
                for key in sub_module.final_stats:
                    if key in self.final_stats:
                        self.final_stats[key] += sub_module.final_stats[key]
                    else:
                        self.final_stats[key] = sub_module.final_stats[key]

    def dump_stats(self):
        if self.stat_type == 'show':
            print("%s: " % self.path)
            for key in self.final_stats:
                print("\t%s: %s" % (key, self.final_stats[key]))
        for sub_module in self.sub_modules:
            sub_module.dump_stats()

    def register_modules(self):
        for attr in vars(self).values():
            if issubclass(type(attr), Module):
                self.sub_modules.append(attr)
            elif issubclass(type(attr), ModuleList):
                self.sub_modules += attr.register()

    def tick(self):
        pass

    def reset(self):
        pass

    def __tick__(self):
        self.tick()
        for sub_module in self.sub_modules:
            sub_module.__tick__()

    def __ntick__(self):
        for sub_module in self.sub_modules:
            sub_module.__ntick__()

    def __reset__(self):
        self.reset()
        for sub_module in self.sub_modules:
            sub_module.__reset__()

class ModuleList(object):
    def __init__(self):
        self.list = []

    def append(self, m):
        if issubclass(type(m), Module) or issubclass(type(m), ModuleList):
            self.list.append(m)
        else:
            raise HWError("Can only append Module or ModuleList")

    def __getitem__(self, key):
        return self.list[key]


    def register(self):
        module_list = []
        for m in self.list:
            if issubclass(type(m), Module):
                module_list.append(m)
            elif issubclass(type(m), ModuleList):
                module_list += m.register()
        return module_list


