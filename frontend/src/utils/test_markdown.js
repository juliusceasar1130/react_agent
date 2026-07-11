import fs from 'fs';
import assert from 'assert';

// 1. 读取真实的 markdown.ts 源码
const tsSource = fs.readFileSync('frontend/src/utils/markdown.ts', 'utf8');

// 2. 用正则截取 extractMetaData 源码定义
const funcMatch = tsSource.match(/export const extractMetaData = \([\s\S]+?return \{ cleanContent, meta \}\s*\n\}/);
if (!funcMatch) {
  throw new Error("Could not find extractMetaData definition in markdown.ts!");
}

// 3. 去除 TypeScript 类型以生成合法 JS
let jsCode = funcMatch[0]
  .replace(/export const extractMetaData/, 'extractMetaData')
  .replace(/:\s*string/g, '')
  .replace(/:\s*\{\s*cleanContent[\s\S]+?\}/g, '')
  .replace(/:\s*MessageMetaData/g, '');

let extractMetaData;
eval(jsCode);

try {
  // 测试用例 1: 图 1 格式 (顿号分隔的多表名 + 逗号残留物)
  const test1 = "关键说明：\nL2 面漆储存线缺陷均值较高。\n数据来源: fct.fct_vehicle_position_current, fct.fct_vehicle_defect_detection, 查询时间: 2026-07-11 18:33:41";
  const { cleanContent: c1, meta: m1 } = extractMetaData(test1);
  assert.strictEqual(c1, "关键说明：\nL2 面漆储存线缺陷均值较高。");
  assert.strictEqual(m1.queryTime, "2026-07-11 18:33:41");
  assert.strictEqual(m1.dataSource, "fct.fct_vehicle_position_current, fct.fct_vehicle_defect_detection");

  // 测试用例 2: 图 2 格式 (中文冒号/全角逗号/括号中文解释)
  const test2 = "L2面漆区域在制车辆与缺陷汇总\n数据来源： fct.fct_vehicle_position_current (实时在制位置) ， fct.fct_vehicle_defect_detection (缺陷检测事实) ， 查询时间：2026-07-11 18:33\n表格内容";
  const { cleanContent: c2, meta: m2 } = extractMetaData(test2);
  assert.strictEqual(c2, "L2面漆区域在制车辆与缺陷汇总\n\n表格内容");
  assert.strictEqual(m2.queryTime, "2026-07-11 18:33");
  assert.strictEqual(m2.dataSource, "fct.fct_vehicle_position_current (实时在制位置) ， fct.fct_vehicle_defect_detection (缺陷检测事实)");

  // 测试用例 3: 图 4 格式 (全角逗号空格表名)
  const test3 = "说明如下：\n数据来源： fct.fct_vehicle_position_current ， mart.mart_vehicle_quality_360 ， 查询时间： 2026-07-11 18:35:14";
  const { cleanContent: c3, meta: m3 } = extractMetaData(test3);
  assert.strictEqual(c3, "说明如下：");
  assert.strictEqual(m3.queryTime, "2026-07-11 18:35:14");
  assert.strictEqual(m3.dataSource, "fct.fct_vehicle_position_current ， mart.mart_vehicle_quality_360");

  // 测试用例 4: 带有句号和逗号残留格式
  const test4 = "说明如下：\n数据来源： fct.fct_vehicle_position_current 关联 mart.mart_vehicle_quality_360, 。 查询时间： 2026-07-11 18:35:14";
  const { cleanContent: c4, meta: m4 } = extractMetaData(test4);
  assert.strictEqual(c4, "说明如下：");
  assert.strictEqual(m4.queryTime, "2026-07-11 18:35:14");
  assert.strictEqual(m4.dataSource, "fct.fct_vehicle_position_current 关联 mart.mart_vehicle_quality_360");

  console.log("PASS: 真实 markdown.ts 中的 extractMetaData 源码单元测试全量通过！");
} catch (e) {
  console.error("FAIL:", e);
  process.exit(1);
}
