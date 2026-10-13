import { useState } from 'react'
import { Alert, Badge, Button, Card, Checkbox, EmptyState, FormAlert, Icon, ICON_NAMES, IconButton, Modal, Pagination, Select, Spinner, Table, Textarea, TextField } from '../components/ui'
import { useDocumentTitle } from '../lib/useDocumentTitle'
export function DesignSystemPage() {
 useDocumentTitle('Design system')
 const [open, setOpen] = useState(false)
 const [page, setPage] = useState(1)
 const [notes, setNotes] = useState('')
 return <section className="mx-auto flex max-w-5xl flex-col gap-6">
  <h1>Design system</h1><p className="text-ink-600">Sijil UI foundations. All examples are demonstration data.</p>
  <Card title="Palette and typography"><div className="flex flex-wrap gap-3"><Badge variant="brand">Brand teal · #126150</Badge><Badge>Ink · #161a21</Badge><Badge variant="success">Success</Badge><Badge variant="warning">Warning</Badge><Badge variant="danger">Danger</Badge><Badge variant="info">Info</Badge></div><p className="mt-4">Segoe UI / system sans · Heading 28px, section 20px, body 16px, helper 14px.</p><p className="font-mono">VIN: DEMO-001</p></Card>
  <Card title="Buttons and progress"><div className="flex flex-wrap items-center gap-3">{(['primary','secondary','ghost','danger'] as const).map(variant=><Button key={variant} variant={variant}>{variant}</Button>)}<Button disabled>Disabled</Button><Button loading>Saving</Button><IconButton icon="plus" label="Add example" /><Spinner /></div></Card>
  <Card title="Form controls"><div className="grid gap-4 sm:grid-cols-2"><TextField label="Name" hint="Your full name" /><TextField label="Invalid email" error="Enter a valid email" /><Select label="Example role" options={[{value:'consumer',label:'Consumer'}]} /><Textarea label="Notes" maxLength={120} value={notes} onChange={e=>setNotes(e.target.value)} /><Checkbox label="Receive updates" description="Optional example" /><TextField label="Disabled field" disabled /></div></Card>
  <Card title="Alerts"><div className="flex flex-col gap-3"><Alert variant="success">Saved successfully</Alert><Alert variant="warning">Check the mileage</Alert><Alert>Demo information</Alert><FormAlert message="Example form error" /></div></Card>
  <Card title="Records"><Table caption="Example records" columns={[{key:'name',header:'Record',render:(r:{id:string;name:string})=>r.name}]} rows={[{id:String(page),name:`Demo record ${page}`}]} rowKey={r=>r.id} /><div className="mt-4"><Pagination total={3} pageSize={1} page={page} onPageChange={setPage} /></div><EmptyState title="No matching records" description="Change the filters to try again" /></Card>
  <Card title="Modal"><Button onClick={()=>setOpen(true)}>Open modal</Button><Modal open={open} title="Example modal" onClose={()=>setOpen(false)} footer={<Button onClick={()=>setOpen(false)}>Done</Button>}><p>Escape, Close, or a backdrop click dismisses this native dialog.</p></Modal></Card>
  <Card title="Icons"><div className="grid grid-cols-3 gap-4 sm:grid-cols-6">{ICON_NAMES.map(name=><div key={name} className="flex flex-col items-center gap-2 text-xs text-ink-600"><Icon name={name} /><span>{name}</span></div>)}</div></Card>
 </section>
}
