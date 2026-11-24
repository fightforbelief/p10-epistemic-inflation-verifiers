import fs from "node:fs/promises";
import { Workbook, SpreadsheetFile } from "@oai/artifact-tool";

const [roster, destination, preview] = process.argv.slice(2);
const rows = (await fs.readFile(roster, "utf8")).trimEnd().split("\n").map(JSON.parse);
const wb = Workbook.create();
const guide = wb.worksheets.add("填写说明");
const groups = [
  ["Modal", "modal_strengthen", 200], ["Hedge", "hedge_adverb_drop", 150],
  ["Scope", "scope_drop"], ["Causal", "causal_upgrade"], ["Quantifier", "quantifier_inflate"],
  ["Weaken", "weaken"], ["Negate", "negate"],
];
const source = "SciFact · Wadden et al. (2020) · https://scifact.apps.allenai.org/";
const instructions = [
  ["P10  |  科学主张盲标", "逐行比较原句、改写和证据摘要"],
  ["提交", "保留未填原件，另存填写副本。只改淡黄色单元格，保持题号和原始顺序。请告知标注人是否事先了解研究假设。"],
  ["主类别", "Modal 和 Hedge 均从第一题顺序填写。当「累计有效」首次分别达到 200 或 150，当页即停止。如始终未达到，填到该页末行。其他页全部填写。"],
  ["Q1  改写质量", "ok = 通顺且编辑完好。minor = 措辞略别扭，含义可判。broken = 语法、时间指向或内容变化使原定比较无法成立。broken 行只答 Q1。"],
  ["Q2  说得更强", "只比较原句与改写。yes = 提高确定性、扩大范围或加强因果；no = 没有加强；contested = 有两种合理读法。若相关改成因果，原句没有作因果断言，选 yes。"],
  ["Q3  摘要能否支持改写", "通读该行完整摘要，包括原句以外的证据。yes = 摘要足以支持该措辞；no = 不足；unclear = 无法判清。根据文中证据作答，勿用外部知识补足。"],
  ["Q4  仅 Scope 页", "generic = 读起来是一般性陈述；existential = 只主张在某些情形出现；ambiguous = 两种读法均合理。"],
  ["Weaken 和 Negate", "只填 C1。Weaken 检查原句能否支持削弱后的句子。Negate 检查原句能否支持负向改写。有效的 Negate 应当缺乏支持，可以是明显矛盾，也可以是证据不足。"],
  ["C1  选项", "as_intended = 改写通顺且符合该页关系；not_as_intended = 改写通顺但关系不符；broken = 改写已坏。"],
  ["阅读", "B 列同一格上半为原句，下半为改写。C 列为完整摘要。必要时拉高行高或在编辑栏展开文字。备注栏可简记判断困难的原因。"],
  ["来源", source],
];
guide.getRange("A1:B11").values = instructions;
guide.getRange("A1:A11").format.columnWidth = 26;
guide.getRange("B1:B11").format.columnWidth = 89;
guide.getRange("A1:B11").format.wrapText = true;
guide.getRange("A1:B11").format.rowHeight = 56;
guide.getRange("A2:A11").format.fill = "#E4EFF1";
const header = range => {
  range.format.fill = "#174D56";
  range.format.font = {name:"Arial", bold:true, color:"#FFFFFF", size:11};
  range.format.rowHeight = 32;
};
header(guide.getRange("A1:B1"));
guide.showGridLines = false;
for (const [name, edit, target] of groups) {
  const ws = wb.worksheets.add(name);
  const group = rows.filter(r=>r.edit === edit);
  const n = group.length + 1;
  const ctl = ["weaken", "negate"].includes(edit);
  const labels = ["题号", "原句  /  改写", "完整证据摘要", ctl ? "C1 对照" : "Q1 质量",
                  "Q2 更强", "Q3 支持", "Q4 范围", "累计有效", "备注"];
  ws.getRange("A1:I1").values = [labels];
  header(ws.getRange("A1:I1"));
  ws.getRange("A2:C"+n).values = group.map(r => [r.id, "原句\n"+r.source+"\n\n改写\n"+r.edited, r.abstract]);
  for (const [i,width] of [23,53,74,15,15,15,16,13,26].entries()) {
    ws.getRangeByIndexes(0,i,n,1).format.columnWidth = width;
  }
  const body = ws.getRange("A2:I"+n);
  body.format.font = {name:"Arial",size:10,color:"#192F36"};
  body.format.verticalAlignment = "top";
  body.format.wrapText = true;
  // Excel caps height at 409 points. The complete abstract is always kept in C.
  group.forEach((r,i) => {
    ws.getRangeByIndexes(i+1,0,1,9).format.rowHeight = Math.min(408, Math.max(115,
        Math.ceil(r.abstract.length/72)*15+28, (Math.ceil(r.source.length/49)+Math.ceil(r.edited.length/49)+4)*15));
  });
  body.format.borders = {insideHorizontal:{style:"thin", color:"#D6DFE0"}};
  const fields = ctl ? [["D",["as_intended","not_as_intended","broken"]]] :
    [["D",["ok","minor","broken"]],["E",["yes","no","contested"]],["F",["no","yes","unclear"]]];
  if (name === "Scope") fields.push(["G",["generic","existential","ambiguous"]]);
  for (const [c,values] of fields) {
    const range = ws.getRange(c+"2:"+c+n);
    range.format.fill = "#FFF2BF";
    range.dataValidation = {rule:{type:"list",values}};
  }
  ws.getRange("I2:I"+n).format.fill = "#FFF2BF";
  if (target) {
    ws.getRange("H2:H"+n).formulas = group.map((_,i) => {
      const x=i+2, previous=i ? "H"+(x-1) : "0";
      return ['=IF(D'+x+'="","",SUM('+previous+',IF(AND(OR(D'+x+'="ok",D'+x+'="minor"),E'+x+'="yes",F'+x+'="no"),1,0)))'];
    });
  }
  ws.freezePanes.freezeRows(1);
  ws.showGridLines = false;
}
const file = await SpreadsheetFile.exportXlsx(wb);
await file.save(destination);
if (preview) {
  const img = await wb.render({sheetName:"填写说明",range:"A1:B6",scale:1.25,format:"png"});
  await fs.writeFile(preview,new Uint8Array(await img.arrayBuffer()));
}
