// Run inside the web container: node setup-comparison.cjs
const fs = require('fs');
const ts = require('typescript');
async function main() {
  const source = fs.readFileSync('src/components/workflow/WorkflowDashboard.tsx', 'utf8');
  const template = source.slice(source.indexOf('const chunkOutputSchema'), source.indexOf('const goldenSample'));
  const definition = new Function(ts.transpile(template) + ';return ragDefinition;')();
  definition.name = 'Golden - Writeup | Parse, RAG, Compare';
  const response = await fetch('http://api:8000/workflows', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ definition, description: 'Nhập golden và writeup, chạy để phân đoạn, truy vấn và so sánh.' }),
  });
  if (!response.ok) throw new Error(await response.text());
  const workflow = await response.json();
  console.log(JSON.stringify({ id: workflow.id, name: workflow.name }));
}
main().catch(error => { console.error(error); process.exitCode = 1; });
