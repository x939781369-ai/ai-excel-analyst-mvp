def get_field_options(columns):
    """
    根据上传数据的列名，生成字段映射选项
    """
    options = ["-- 请选择 --"] + list(columns)
    return options