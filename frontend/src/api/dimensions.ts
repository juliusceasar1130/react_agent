import api from './index'

export interface DimensionTableData {
  table_name: string
  columns: string[]
  rows: (string | number)[][]
  row_count: number
}

/**
  * 获取指定维度表的数据
  * @param tableName 维度表名
  */
export function getDimensionTableApi(tableName: string): Promise<DimensionTableData> {
  return api.get(`/api/chat/dimensions/${encodeURIComponent(tableName)}`) as Promise<DimensionTableData>
}
