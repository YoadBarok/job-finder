// RULE: CVs contain no hyperlinks; contact details are plain text.
// Usage: node build_cv.js cv.json "<DATA>/jobs/<date>-<company>-<role>/<Name> CV.docx"   then: python3 to_pdf.py "<that .docx>"
// cv.json: name, headline, contact[{t}], profile?, skills?[[label,text]], jobs[{title, meta, bullets[[label,text] | "text"]}],
//          sections?[{title, items[[label,text] | "text"]}] (education, projects, languages, certifications, portfolio...),
//          headings?{profile, skills, jobs}, page? "a4" | "letter"
const fs = require('fs');
process.umask(0o077); // private data: owner-only files
function loadDocx() {
  const path = require('path'), os = require('os');
  const tries = ['docx', path.join(os.homedir(), '.cache/job-finder/node_modules/docx'), path.join(__dirname, '../node_modules/docx')];
  for (const t of tries) { try { return require(t); } catch (e) { /* next */ } }
  return null;
}
const d = loadDocx();
if (process.argv[2] === '--check') process.exit(d ? 0 : 1);
if (!d) { console.error('Missing the docx library. Run: npm install --prefix ~/.cache/job-finder docx'); process.exit(1); }
const { Document, Packer, Paragraph, TextRun, LevelFormat } = d;
const cv = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
// Guard: never build a CV from template data (facts must come from the approved base CV).
if (/ALEX EXAMPLE/i.test(cv.name) || /Example Corp/.test(JSON.stringify(cv.jobs))) {
  console.error('Refusing: this CV is still the template. Run /setup to create and approve the base CV first.');
  process.exit(1);
}
const F = cv.font || 'Inter', BODY = '334155', DARK = '0F172A', BLUE = '2563EB';
const pt = n => n * 2; // half-points
const r = (text, o = {}) => new TextRun({ text, font: F, size: pt(o.size || 8), bold: !!o.bold, color: o.color || BODY });
const kids = [];
kids.push(new Paragraph({ spacing: { after: 0 }, children: [r(cv.name, { size: 15, bold: true, color: DARK })] }));
kids.push(new Paragraph({ spacing: { after: 20 }, children: [r(cv.headline, { size: 8.5, bold: true, color: BLUE })] }));
const contact = [];
cv.contact.forEach((c, i) => {
  if (i) contact.push(r(' | '));
  contact.push(r(c.t)); // RULE: no hyperlinks anywhere in the CV - plain text only (ATS)
});
kids.push(new Paragraph({ spacing: { after: 240 }, children: contact }));
const heading = t => new Paragraph({ keepNext: true, spacing: { before: 0, after: 40 }, children: [r(t, { size: 9.5, bold: true, color: DARK })] });
const bullet = (label, text) => new Paragraph({ numbering: { reference: 'b', level: 0 }, spacing: { after: 60, line: 196, lineRule: 'exact' }, children: [r(label + ': ', { bold: true }), r(text)] });
const H = Object.assign({ profile: 'PROFILE', skills: 'SKILLS', jobs: 'EMPLOYMENT HISTORY' }, cv.headings || {});
const item = (x) => Array.isArray(x) ? bullet(x[0], x[1]) : new Paragraph({ numbering: { reference: 'b', level: 0 }, spacing: { after: 60, line: 196, lineRule: 'exact' }, children: [r(String(x))] });
const gap = () => kids.push(new Paragraph({ spacing: { after: 200 }, children: [] }));
if (cv.profile) {
  kids.push(heading(H.profile));
  kids.push(new Paragraph({ spacing: { after: 240, line: 196, lineRule: 'exact' }, children: [r(cv.profile)] }));
}
if (cv.skills && cv.skills.length) {
  kids.push(heading(H.skills));
  cv.skills.forEach(x => kids.push(item(x)));
  gap();
}
kids.push(heading(H.jobs));
cv.jobs.forEach(j => {
  kids.push(new Paragraph({ keepNext: true, spacing: { before: 20, after: 40 }, children: [r(j.title, { size: 8.5, bold: true }), r(' | ', { size: 8.5 }), r(j.meta, { size: 8.5 })] }));
  (j.bullets || []).forEach(x => kids.push(item(x)));
});
(cv.sections || []).forEach(sec => {
  gap();
  kids.push(heading(String(sec.title).toUpperCase()));
  (sec.items || []).forEach(x => kids.push(item(x)));
});
const doc = new Document({
  creator: cv.name, title: cv.name.split(' ').map(w => w[0] + w.slice(1).toLowerCase()).join(' ') + ' - CV',
  styles: { default: { document: { run: { font: F, size: pt(8), color: BODY } } } },
  numbering: { config: [{ reference: 'b', levels: [{ level: 0, format: LevelFormat.BULLET, text: '●', alignment: 'left',
    style: { run: { font: 'Arial', size: pt(7), color: '000000' }, paragraph: { indent: { left: 720, hanging: 360 } } } }] }] },
  sections: [{ properties: { page: { size: cv.page === 'letter' ? { width: 12240, height: 15840 } : { width: 11906, height: 16838 }, margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } }, children: kids }]
});
Packer.toBuffer(doc).then(b => fs.writeFileSync(process.argv[3], b));
