import { useRef, useState } from 'react'
import { BookOpen, Eye, FileUp, Loader2, RefreshCw, Search, Trash2 } from 'lucide-react'
import { useMutation } from '@tanstack/react-query'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent } from '@/components/ui/dialog'
import { FieldError, FieldHint, Input, Label, Select } from '@/components/ui/form-controls'
import { ConfirmDialog } from '@/components/common/ConfirmDialog'
import { EmptyState, ErrorState, LoadingRows, Notice, PageHeader } from '@/components/common/States'
import { useDocumentAction, useDocumentChunks, useDocuments, useUploadDocument } from '@/hooks/useApi'
import { api, getErrorMessage } from '@/services/api'
import { EQUIPMENT_TYPES, formatDateTime } from '@/utils/format'

const TYPES = { ...EQUIPMENT_TYPES, general: 'General' }
const STATUS_TONE = { pending: 'slate', processing: 'blue', completed: 'green', failed: 'red' }
const MAX_MB = 10

function UploadCard() {
  const upload = useUploadDocument()
  const fileRef = useRef(null)
  const [file, setFile] = useState(null)
  const [title, setTitle] = useState('')
  const [type, setType] = useState('pump')
  const [error, setError] = useState(null)

  const submit = (e) => {
    e.preventDefault()
    if (!file) return setError('Choose a PDF or TXT file')
    if (!/\.(pdf|txt)$/i.test(file.name)) return setError('Only .pdf and .txt files are supported')
    if (file.size > MAX_MB * 1024 * 1024) return setError(`File must be smaller than ${MAX_MB} MB`)
    setError(null)
    const form = new FormData()
    form.append('file', file)
    form.append('equipment_type', type)
    if (title.trim()) form.append('title', title.trim())
    upload.mutate(form, {
      onSuccess: () => { setFile(null); setTitle(''); if (fileRef.current) fileRef.current.value = '' },
    })
  }

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Upload document</CardTitle>
          <CardDescription>PDF or TXT, up to {MAX_MB} MB. Text is extracted, chunked and embedded for semantic search.</CardDescription>
        </div>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="space-y-4" noValidate>
          {upload.isError && <Notice tone="danger" title="Upload failed">{getErrorMessage(upload.error)}</Notice>}
          {upload.isSuccess && <Notice tone="success" title="Uploaded">Indexing “{upload.data.title}” — status updates below.</Notice>}
          <div>
            <Label htmlFor="kb-file" required>File</Label>
            <Input id="kb-file" ref={fileRef} type="file" accept=".pdf,.txt,application/pdf,text/plain" className="py-1.5"
              onChange={(e) => setFile(e.target.files?.[0] || null)} aria-invalid={!!error} />
            <FieldError message={error} />
            <FieldHint>Scanned PDFs without a text layer cannot be indexed.</FieldHint>
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <Label htmlFor="kb-title">Title</Label>
              <Input id="kb-title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Defaults to file name" />
            </div>
            <div>
              <Label htmlFor="kb-type" required>Equipment type</Label>
              <Select id="kb-type" value={type} onChange={(e) => setType(e.target.value)}>
                {Object.entries(TYPES).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </Select>
            </div>
          </div>
          <div className="flex justify-end">
            <Button type="submit" loading={upload.isPending}><FileUp /> Upload</Button>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}

function SearchCard() {
  const [query, setQuery] = useState('')
  const [type, setType] = useState('')
  const search = useMutation({ mutationFn: api.searchKnowledge })
  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Test retrieval</CardTitle>
          <CardDescription>Run the same semantic search used during triage.</CardDescription>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <form className="flex flex-col gap-2 sm:flex-row" onSubmit={(e) => { e.preventDefault(); if (query.trim().length >= 3) search.mutate({ query, equipment_type: type || null, top_k: 4 }) }}>
          <Input placeholder="e.g. grinding noise from bearing" value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Search query" />
          <Select className="sm:w-44" value={type} onChange={(e) => setType(e.target.value)} aria-label="Equipment type">
            <option value="">All types</option>
            {Object.entries(EQUIPMENT_TYPES).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </Select>
          <Button type="submit" variant="outline" loading={search.isPending} disabled={query.trim().length < 3}><Search /> Search</Button>
        </form>
        {search.isError && <ErrorState error={search.error} />}
        {search.data && search.data.status !== 'ok' && <Notice tone="warning">{search.data.message}</Notice>}
        {search.data?.chunks?.map((c) => (
          <div key={c.chunk_id} className="rounded-lg border border-slate-200 p-3">
            <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
              <span className="font-medium text-slate-900">{c.document_title}{c.page_number ? ` · p.${c.page_number}` : ''}</span>
              <span className="text-slate-500" title="Cosine similarity — not a probability">text relevance {c.score.toFixed(2)}</span>
            </div>
            <p className="mt-1 line-clamp-4 whitespace-pre-line text-sm text-slate-600">{c.text}</p>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}

function ChunksDialog({ doc, onClose }) {
  const chunks = useDocumentChunks(doc?.document_id)
  return (
    <Dialog open={!!doc} onOpenChange={(o) => !o && onClose()}>
      {doc && (
        <DialogContent title={doc.title} description={`${doc.chunk_count} indexed chunk(s) · ${doc.source}`} className="max-w-2xl">
          {chunks.isLoading && <LoadingRows rows={3} />}
          {chunks.isError && <ErrorState error={chunks.error} />}
          <ol className="space-y-3">
            {chunks.data?.map((c) => (
              <li key={c.chunk_id} className="rounded-lg border border-slate-200 p-3">
                <p className="font-mono text-[11px] text-slate-400">{c.chunk_id}{c.page_number ? ` · page ${c.page_number}` : ''}</p>
                <p className="mt-1 whitespace-pre-line text-sm text-slate-700">{c.text}</p>
              </li>
            ))}
          </ol>
        </DialogContent>
      )}
    </Dialog>
  )
}

export default function KnowledgeBase() {
  const docs = useDocuments()
  const reindex = useDocumentAction(api.reindexDocument)
  const remove = useDocumentAction(api.deleteDocument)
  const [viewing, setViewing] = useState(null)
  const [deleting, setDeleting] = useState(null)

  return (
    <>
      <PageHeader title="Knowledge base" description="Maintenance manuals used as cited evidence during triage." />
      <Notice tone="warning" className="mb-6" title="Sample manuals are fictional">
        Seeded documents (AquaFlow, ClimaCore, DriveMax) were written for this demo and contain illustrative values only.
      </Notice>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <div className="space-y-6 xl:col-span-2">
          <Card>
            <CardHeader>
              <div>
                <CardTitle>Documents</CardTitle>
                <CardDescription>Ingestion status refreshes automatically while indexing.</CardDescription>
              </div>
            </CardHeader>
            {docs.isError && <CardContent><ErrorState error={docs.error} onRetry={docs.refetch} /></CardContent>}
            {docs.isLoading && <CardContent><LoadingRows /></CardContent>}
            {docs.data?.length === 0 && <CardContent><EmptyState icon={BookOpen} title="No documents yet" description="Upload a manual to enable cited evidence." /></CardContent>}
            {docs.data?.length > 0 && (
              <ul className="divide-y divide-slate-100">
                {docs.data.map((d) => (
                  <li key={d.document_id} className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="truncate text-sm font-medium text-slate-900">{d.title}</p>
                        {d.is_sample && <Badge tone="amber">Fictional sample</Badge>}
                      </div>
                      <p className="mt-0.5 text-xs text-slate-500">
                        {TYPES[d.equipment_type]} · {d.document_type.toUpperCase()} · {d.page_count} page(s) · {d.chunk_count} chunk(s) · {formatDateTime(d.created_at)}
                      </p>
                      {d.error && <p className="mt-1 text-xs text-red-600">{d.error}</p>}
                    </div>
                    <div className="flex items-center gap-1">
                      <Badge tone={STATUS_TONE[d.ingestion_status]}>
                        {['pending', 'processing'].includes(d.ingestion_status) && <Loader2 className="size-3 animate-spin" />}
                        {d.ingestion_status}
                      </Badge>
                      <Button variant="ghost" size="icon" aria-label={`View chunks of ${d.title}`} disabled={d.ingestion_status !== 'completed'} onClick={() => setViewing(d)}><Eye /></Button>
                      <Button variant="ghost" size="icon" aria-label={`Re-index ${d.title}`} onClick={() => reindex.mutate(d.document_id)}><RefreshCw /></Button>
                      <Button variant="ghost" size="icon" aria-label={`Delete ${d.title}`} onClick={() => setDeleting(d)}><Trash2 /></Button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Card>
          <SearchCard />
        </div>
        <UploadCard />
      </div>

      <ChunksDialog doc={viewing} onClose={() => setViewing(null)} />
      <ConfirmDialog
        open={!!deleting}
        onOpenChange={(o) => !o && setDeleting(null)}
        title="Delete document?"
        description={`“${deleting?.title}” and its vectors will be removed. Past analyses keep their stored excerpts.`}
        confirmLabel="Delete"
        confirmVariant="destructive"
        loading={remove.isPending}
        onConfirm={() => remove.mutate(deleting.document_id, { onSuccess: () => setDeleting(null) })}
      >
        {remove.isError && <Notice tone="danger">{getErrorMessage(remove.error)}</Notice>}
      </ConfirmDialog>
    </>
  )
}
