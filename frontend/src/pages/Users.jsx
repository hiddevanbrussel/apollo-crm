import { useCallback, useEffect, useState } from "react";
import api, { apiError } from "../api/client";
import { Icon } from "../components/icons";
import { EmptyState, Field, Modal, PageLoader, Spinner } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";

const EMPTY = { name: "", email: "", password: "", role: "user" };

function RoleBadge({ role }) {
  const isAdmin = role === "admin";
  return (
    <span
      className={`badge ${isAdmin ? "bg-purple-50 text-purple-700" : "bg-ink-100 text-ink-600"}`}
    >
      {isAdmin ? "Admin" : "User"}
    </span>
  );
}

export default function Users() {
  const toast = useToast();
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/users");
      setUsers(data.items);
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    load();
  }, [load]);

  const openCreate = () => {
    setEditing(null);
    setForm(EMPTY);
    setShowForm(true);
  };

  const openEdit = (u) => {
    setEditing(u);
    setForm({ name: u.name, email: u.email, password: "", role: u.role });
    setShowForm(true);
  };

  const save = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      if (editing) {
        const payload = { name: form.name, email: form.email, role: form.role };
        if (form.password) payload.password = form.password;
        await api.put(`/users/${editing.id}`, payload);
        toast.success("User updated.");
      } else {
        await api.post("/users", form);
        toast.success("User created.");
      }
      setShowForm(false);
      load();
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setSaving(false);
    }
  };

  const remove = async (u) => {
    if (!confirm(`Delete user ${u.name}?`)) return;
    try {
      await api.delete(`/users/${u.id}`);
      toast.success("User deleted.");
      load();
    } catch (err) {
      toast.error(apiError(err));
    }
  };

  if (loading) return <PageLoader />;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-ink-900">Users</h1>
          <p className="text-sm text-ink-500">
            Manage who can access Apollo CRM. Admins configure integrations; users enrich companies and contacts.
          </p>
        </div>
        <button className="btn-primary" onClick={openCreate}>
          <Icon.Plus width={18} height={18} /> New user
        </button>
      </div>

      <div className="card overflow-hidden">
        {users.length === 0 ? (
          <EmptyState title="No users yet" description="Create the first user account." />
        ) : (
          <table className="w-full text-left text-sm">
            <thead className="border-b border-ink-100 bg-ink-50/80 text-xs font-semibold uppercase tracking-wide text-ink-400">
              <tr>
                <th className="px-4 py-3">Name</th>
                <th className="px-4 py-3">Email</th>
                <th className="px-4 py-3">Role</th>
                <th className="px-4 py-3">Created</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-100">
              {users.map((u) => (
                <tr key={u.id} className="hover:bg-ink-50/50">
                  <td className="px-4 py-3 font-medium text-ink-900">{u.name}</td>
                  <td className="px-4 py-3 text-ink-600">{u.email}</td>
                  <td className="px-4 py-3">
                    <RoleBadge role={u.role} />
                  </td>
                  <td className="px-4 py-3 text-ink-500">
                    {new Date(u.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex justify-end gap-1">
                      <button className="btn-ghost px-2 py-1.5" onClick={() => openEdit(u)} title="Edit">
                        <Icon.Edit width={16} height={16} />
                      </button>
                      <button
                        className="btn-ghost px-2 py-1.5 text-red-600 hover:bg-red-50"
                        onClick={() => remove(u)}
                        disabled={u.id === currentUser?.id}
                        title={u.id === currentUser?.id ? "Cannot delete yourself" : "Delete"}
                      >
                        <Icon.Trash width={16} height={16} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <Modal
        open={showForm}
        onClose={() => setShowForm(false)}
        title={editing ? "Edit user" : "New user"}
      >
        <form onSubmit={save} className="space-y-4">
          <Field label="Name" required>
            <input
              className="input"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              required
            />
          </Field>
          <Field label="Email" required>
            <input
              type="email"
              className="input"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              required
            />
          </Field>
          <Field label={editing ? "New password (optional)" : "Password"} required={!editing}>
            <input
              type="password"
              className="input"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              required={!editing}
              minLength={6}
              autoComplete="new-password"
            />
          </Field>
          <Field label="Role">
            <select
              className="input"
              value={form.role}
              onChange={(e) => setForm({ ...form, role: e.target.value })}
            >
              <option value="user">User — companies & contacts, Apollo enrich</option>
              <option value="admin">Admin — settings, users, all features</option>
            </select>
          </Field>
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" className="btn-secondary" onClick={() => setShowForm(false)}>
              Cancel
            </button>
            <button type="submit" className="btn-primary" disabled={saving}>
              {saving && <Spinner className="h-4 w-4 border-white/40 border-t-white" />}
              {editing ? "Save" : "Create"}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
