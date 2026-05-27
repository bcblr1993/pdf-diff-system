import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Key, Webhook as WebhookIcon, Plus, Trash2, Copy, Power, Activity, X, CheckCircle2, XCircle, Clock,
} from "lucide-react";
import {
  listApiKeys, createApiKey, disableApiKey, deleteApiKey,
  listWebhooks, createWebhook, updateWebhook, deleteWebhook, listWebhookDeliveries,
} from "@/api/endpoints";
import { errMsg } from "@/api/client";
import { fmtAgo, fmtTime } from "@/lib/utils";
import { useAuthStore } from "@/stores/auth";
import type { WebhookEvent } from "@/types";


const EVENT_LABEL: Record<WebhookEvent, string> = {
  "comparison.done": "对比完成",
  "comparison.failed": "对比失败",
  "batch.done": "批量任务完成",
};

export default function Integrations() {
  const user = useAuthStore((s) => s.user);
  const [tab, setTab] = useState<"keys" | "hooks">("keys");

  if (user?.role !== "admin") {
    return (
      <div className="max-w-3xl mx-auto p-6 text-center text-gray-500">
        <Key className="w-10 h-10 mx-auto mb-2 text-gray-300" />
        <div>本页仅管理员可见</div>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto p-6">
      <h1 className="text-xl font-semibold mb-1">集成中心</h1>
      <p className="text-sm text-gray-500 mb-4">API Key 用于外部系统调用 /api/v1 端点；Webhook 用于推送任务完成事件。</p>

      <div className="card p-1 mb-4 inline-flex">
        <button
          onClick={() => setTab("keys")}
          className={`px-4 py-2 rounded-md text-sm font-medium ${
            tab === "keys" ? "bg-blue-600 text-white" : "text-gray-600 hover:bg-gray-100"
          }`}
        >
          <Key className="w-3.5 h-3.5 inline-block mr-1" /> API Keys
        </button>
        <button
          onClick={() => setTab("hooks")}
          className={`px-4 py-2 rounded-md text-sm font-medium ${
            tab === "hooks" ? "bg-blue-600 text-white" : "text-gray-600 hover:bg-gray-100"
          }`}
        >
          <WebhookIcon className="w-3.5 h-3.5 inline-block mr-1" /> Webhooks
        </button>
      </div>

      {tab === "keys" ? <ApiKeysPanel /> : <WebhooksPanel />}
    </div>
  );
}

// ─────────── API Keys 面板 ───────────

function ApiKeysPanel() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["api-keys"], queryFn: listApiKeys });
  const [creating, setCreating] = useState(false);
  const [createdKey, setCreatedKey] = useState<string | null>(null);

  const createMut = useMutation({
    mutationFn: createApiKey,
    onSuccess: (r) => {
      setCreatedKey(r.full_key);
      qc.invalidateQueries({ queryKey: ["api-keys"] });
      toast.success("已创建");
    },
    onError: (e) => toast.error(errMsg(e)),
  });
  const disableMut = useMutation({
    mutationFn: disableApiKey,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["api-keys"] }); toast.success("已吊销"); },
  });
  const delMut = useMutation({
    mutationFn: deleteApiKey,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["api-keys"] }); toast.success("已删除"); },
  });

  const items = data?.items || [];

  return (
    <>
      {createdKey && (
        <div className="card p-4 mb-4 bg-amber-50 border-amber-300">
          <div className="font-medium text-amber-900 mb-2">⚠ 完整 Key 只显示这一次，请立即复制保存：</div>
          <div className="flex items-center gap-2 bg-white p-3 rounded border border-amber-200 font-mono text-sm break-all">
            <span className="flex-1">{createdKey}</span>
            <button
              onClick={() => { navigator.clipboard.writeText(createdKey); toast.success("已复制"); }}
              className="btn-secondary !py-1 !px-2 shrink-0"
            >
              <Copy className="w-3.5 h-3.5" /> 复制
            </button>
            <button onClick={() => setCreatedKey(null)} className="text-gray-400 hover:text-gray-700">
              <X className="w-4 h-4" />
            </button>
          </div>
          <div className="mt-3 text-xs text-amber-900">
            使用方式：调用 API 时在 Header 加 <code className="bg-white px-1 rounded">X-API-Key: {createdKey.slice(0, 24)}...</code>
          </div>
        </div>
      )}

      <div className="card p-4 mb-4">
        {!creating ? (
          <button onClick={() => setCreating(true)} className="btn-primary">
            <Plus className="w-3.5 h-3.5" /> 创建 API Key
          </button>
        ) : (
          <NewKeyForm
            onCancel={() => setCreating(false)}
            onSubmit={(body) => { createMut.mutate(body); setCreating(false); }}
          />
        )}
      </div>

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-gray-600 text-xs uppercase">
            <tr>
              <th className="px-4 py-2 text-left">名称</th>
              <th className="px-4 py-2 text-left">Key 前缀</th>
              <th className="px-4 py-2 text-left">调用次数</th>
              <th className="px-4 py-2 text-left">最后使用</th>
              <th className="px-4 py-2 text-left">状态</th>
              <th className="px-4 py-2 text-left">创建</th>
              <th className="px-4 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {items.length === 0 && (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-400">暂无 API Key</td></tr>
            )}
            {items.map((k) => (
              <tr key={k.id} className="border-t">
                <td className="px-4 py-3 font-medium">{k.name}</td>
                <td className="px-4 py-3 font-mono text-xs text-gray-600">{k.key_prefix}***</td>
                <td className="px-4 py-3">{k.call_count}</td>
                <td className="px-4 py-3 text-xs text-gray-500">{k.last_used_at ? fmtAgo(k.last_used_at) : "—"}</td>
                <td className="px-4 py-3">
                  {k.is_active
                    ? <span className="badge bg-green-100 text-green-800">启用</span>
                    : <span className="badge bg-gray-200 text-gray-600">已吊销</span>}
                </td>
                <td className="px-4 py-3 text-xs text-gray-500">{fmtAgo(k.created_at)}</td>
                <td className="px-4 py-3 flex gap-1">
                  {k.is_active && (
                    <button onClick={() => { if (confirm("确认吊销该 Key？")) disableMut.mutate(k.id); }}
                            className="btn-secondary !py-1 !px-2" title="吊销">
                      <Power className="w-3 h-3" />
                    </button>
                  )}
                  <button onClick={() => { if (confirm("确认删除？")) delMut.mutate(k.id); }}
                          className="btn-danger !py-1 !px-2" title="删除">
                    <Trash2 className="w-3 h-3" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function NewKeyForm({ onSubmit, onCancel }: {
  onSubmit: (body: { name: string; expires_at?: string | null }) => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState("");
  const [expiresAt, setExpiresAt] = useState("");
  return (
    <div className="grid grid-cols-2 gap-3">
      <div>
        <label className="label">Key 名称（用于识别用途）</label>
        <input className="input" value={name} onChange={(e) => setName(e.target.value)}
               placeholder="例如：合同系统集成 / OA 推送" autoFocus />
      </div>
      <div>
        <label className="label">过期时间（可选）</label>
        <input className="input" type="datetime-local" value={expiresAt}
               onChange={(e) => setExpiresAt(e.target.value)} />
      </div>
      <div className="col-span-2 flex gap-2 justify-end">
        <button onClick={onCancel} className="btn-secondary">取消</button>
        <button
          onClick={() => {
            if (!name.trim()) { toast.error("请填写名称"); return; }
            onSubmit({ name: name.trim(), expires_at: expiresAt || null });
          }}
          className="btn-primary"
        >
          创建
        </button>
      </div>
    </div>
  );
}

// ─────────── Webhooks 面板 ───────────

function WebhooksPanel() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["webhooks"], queryFn: listWebhooks });
  const [creating, setCreating] = useState(false);
  const [createdSecret, setCreatedSecret] = useState<string | null>(null);
  const [showDeliveries, setShowDeliveries] = useState<number | null>(null);

  const createMut = useMutation({
    mutationFn: createWebhook,
    onSuccess: (r) => {
      setCreatedSecret(r.secret);
      qc.invalidateQueries({ queryKey: ["webhooks"] });
      toast.success("已创建");
    },
    onError: (e) => toast.error(errMsg(e)),
  });
  const updateMut = useMutation({
    mutationFn: ({ id, body }: { id: number; body: any }) => updateWebhook(id, body),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["webhooks"] }); toast.success("已更新"); },
  });
  const delMut = useMutation({
    mutationFn: deleteWebhook,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["webhooks"] }); toast.success("已删除"); },
  });

  const items = data?.items || [];

  return (
    <>
      {createdSecret && (
        <div className="card p-4 mb-4 bg-amber-50 border-amber-300">
          <div className="font-medium text-amber-900 mb-2">⚠ HMAC 签名密钥只显示这一次：</div>
          <div className="flex items-center gap-2 bg-white p-3 rounded border border-amber-200 font-mono text-sm break-all">
            <span className="flex-1">{createdSecret}</span>
            <button onClick={() => { navigator.clipboard.writeText(createdSecret); toast.success("已复制"); }}
                    className="btn-secondary !py-1 !px-2 shrink-0">
              <Copy className="w-3.5 h-3.5" /> 复制
            </button>
            <button onClick={() => setCreatedSecret(null)} className="text-gray-400 hover:text-gray-700">
              <X className="w-4 h-4" />
            </button>
          </div>
          <div className="mt-3 text-xs text-amber-900">
            Webhook 推送时会带 <code className="bg-white px-1 rounded">X-PdfDiff-Signature: sha256=...</code> Header。
            校验方式：<code className="bg-white px-1 rounded">HMAC-SHA256(secret, timestamp + "." + body)</code>
          </div>
        </div>
      )}

      <div className="card p-4 mb-4">
        {!creating ? (
          <button onClick={() => setCreating(true)} className="btn-primary">
            <Plus className="w-3.5 h-3.5" /> 注册 Webhook
          </button>
        ) : (
          <NewHookForm
            onCancel={() => setCreating(false)}
            onSubmit={(body) => { createMut.mutate(body); setCreating(false); }}
          />
        )}
      </div>

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-gray-600 text-xs uppercase">
            <tr>
              <th className="px-4 py-2 text-left">名称</th>
              <th className="px-4 py-2 text-left">URL</th>
              <th className="px-4 py-2 text-left">事件</th>
              <th className="px-4 py-2 text-left">状态</th>
              <th className="px-4 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {items.length === 0 && (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-gray-400">暂无 Webhook</td></tr>
            )}
            {items.map((h) => (
              <tr key={h.id} className="border-t">
                <td className="px-4 py-3 font-medium">{h.name || "(无名)"}</td>
                <td className="px-4 py-3 font-mono text-xs text-gray-600 max-w-[280px] truncate">{h.url}</td>
                <td className="px-4 py-3 text-xs">
                  {h.events_json.map((e) => (
                    <span key={e} className="badge bg-blue-100 text-blue-700 mr-1">{EVENT_LABEL[e as WebhookEvent] || e}</span>
                  ))}
                </td>
                <td className="px-4 py-3">
                  <button
                    onClick={() => updateMut.mutate({ id: h.id, body: { is_active: !h.is_active } })}
                    className={`badge cursor-pointer ${h.is_active ? "bg-green-100 text-green-800" : "bg-gray-200 text-gray-600"}`}
                  >
                    {h.is_active ? "启用" : "已停"}
                  </button>
                </td>
                <td className="px-4 py-3 flex gap-1">
                  <button onClick={() => setShowDeliveries(h.id)} className="btn-secondary !py-1 !px-2"
                          title="投递记录">
                    <Activity className="w-3 h-3" />
                  </button>
                  <button onClick={() => { if (confirm("确认删除？")) delMut.mutate(h.id); }}
                          className="btn-danger !py-1 !px-2">
                    <Trash2 className="w-3 h-3" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showDeliveries && <DeliveriesModal wid={showDeliveries} onClose={() => setShowDeliveries(null)} />}
    </>
  );
}

function NewHookForm({ onSubmit, onCancel }: {
  onSubmit: (body: { name: string; url: string; events: WebhookEvent[] }) => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [events, setEvents] = useState<Set<WebhookEvent>>(new Set(["comparison.done"]));
  const ALL_EVENTS: WebhookEvent[] = ["comparison.done", "comparison.failed", "batch.done"];

  return (
    <div className="space-y-3">
      <div>
        <label className="label">名称</label>
        <input className="input" value={name} onChange={(e) => setName(e.target.value)}
               placeholder="例如：合同系统回调" autoFocus />
      </div>
      <div>
        <label className="label">URL（HTTPS 推荐）</label>
        <input className="input" value={url} onChange={(e) => setUrl(e.target.value)}
               placeholder="https://your-system.example.com/api/pdf-diff/webhook" />
      </div>
      <div>
        <label className="label">订阅事件</label>
        <div className="flex flex-wrap gap-2">
          {ALL_EVENTS.map((e) => (
            <label key={e} className="inline-flex items-center gap-1 text-sm">
              <input
                type="checkbox"
                checked={events.has(e)}
                onChange={(ev) => {
                  const s = new Set(events);
                  if (ev.target.checked) s.add(e); else s.delete(e);
                  setEvents(s);
                }}
              />
              <span className="badge bg-blue-100 text-blue-700">{EVENT_LABEL[e]}</span>
            </label>
          ))}
        </div>
      </div>
      <div className="flex gap-2 justify-end">
        <button onClick={onCancel} className="btn-secondary">取消</button>
        <button
          onClick={() => {
            if (!url.match(/^https?:\/\//)) { toast.error("URL 不合法"); return; }
            if (events.size === 0) { toast.error("至少选 1 个事件"); return; }
            onSubmit({ name: name.trim(), url: url.trim(), events: [...events] });
          }}
          className="btn-primary"
        >
          注册
        </button>
      </div>
    </div>
  );
}

function DeliveriesModal({ wid, onClose }: { wid: number; onClose: () => void }) {
  const { data } = useQuery({
    queryKey: ["webhook-deliveries", wid],
    queryFn: () => listWebhookDeliveries(wid),
    refetchInterval: 3000,
  });
  const items = data?.items || [];
  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-white rounded-lg shadow-xl max-w-3xl w-full max-h-[80vh] overflow-hidden flex flex-col"
           onClick={(e) => e.stopPropagation()}>
        <div className="px-4 py-3 border-b flex items-center">
          <h2 className="font-medium">投递记录 (Webhook #{wid})</h2>
          <button onClick={onClose} className="ml-auto text-gray-400 hover:text-gray-700">
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto">
          {items.length === 0 ? (
            <div className="p-8 text-center text-gray-400 text-sm">暂无投递记录</div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-gray-600 text-xs uppercase sticky top-0">
                <tr>
                  <th className="px-3 py-2 text-left">事件</th>
                  <th className="px-3 py-2 text-left">状态</th>
                  <th className="px-3 py-2 text-left">HTTP</th>
                  <th className="px-3 py-2 text-left">尝试</th>
                  <th className="px-3 py-2 text-left">时间</th>
                </tr>
              </thead>
              <tbody>
                {items.map((d) => (
                  <tr key={d.id} className="border-t">
                    <td className="px-3 py-2 font-mono text-xs">{d.event}</td>
                    <td className="px-3 py-2">
                      {d.status === "success" && <span className="inline-flex items-center gap-1 text-green-700"><CheckCircle2 className="w-3 h-3" /> 成功</span>}
                      {d.status === "failed" && <span className="inline-flex items-center gap-1 text-red-700"><XCircle className="w-3 h-3" /> 失败</span>}
                      {d.status === "pending" && <span className="inline-flex items-center gap-1 text-gray-500"><Clock className="w-3 h-3" /> 处理中</span>}
                    </td>
                    <td className="px-3 py-2">{d.response_status ?? "—"}</td>
                    <td className="px-3 py-2">{d.attempts}</td>
                    <td className="px-3 py-2 text-xs text-gray-500">{fmtTime(d.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
