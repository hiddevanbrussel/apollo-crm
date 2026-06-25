import { useCallback, useEffect, useState } from "react";
import api, { apiError } from "../api/client";
import { Icon } from "../components/icons";
import { EmptyState, Field, Modal, PageLoader, Spinner } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";

const EMPTY_FORM = { name: "", email: "", password: "", role: "user" };

function RoleBadge({ role }) {
  const isAdmin = role === "admin";
  return (
    <span
      className={`badge ${isAdmin ? "bg-brand-50 text-brand-700" : "bg-ink-100 text-ink-600"}`}
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
  const [showCreate, setShowCreate] = useState(false);
  const [editUser, setEditUser] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/users");
      setUsers(data);
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
    setForm(EMPTY_FORM);
    setShowCreate(true);
  };

  const openEdit = (u) => {
    setEditUser(u);
    setForm({ name: u.name, email: u.email, password: "", role: u.role });
  };

  const closeModals = () => {
    setShowCreate(false);
    setEditUser(null);
    setForm(EMPTY_FORM);
  };

  const createUser = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await api.post("/users", form);
      toast.success("User created.");
      closeModals();
      load();
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setSaving(false);
    }
  };

  const updateUser = async (e) => {
    e.preventDefault();
    if (!editUser) return;
    setSaving(true);
    try {
      const payload = { name: form.name, email: form.email, role: form.role };
      if (form.password) payload.password = form.password;
      await api.put(`/users/${editUser.id}`, payload);
      toast.success("User updated.");
      closeModals();
      load();
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setSaving(false);
    }
  };

  const deleteUser = async (u) => {
    if (!confirm(`Delete user ${u.email}?`)) return;
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
          <p className="mt-1 text-sm text-ink-500">Manage who can access Apollo CRM.</p>
        </div>
        <button className="btn-primary" onClick={openCreate}>
          <Icon.Plus width={18} height={18} /> Add user
        </button>
      </div>

      {users.length === 0 ? (
        <EmptyState title="No users yet" description="Create the first user account." />
      ) : (
        <div className="card overflow-hidden">
          <table className="w-full">
            <thead className="border-b border-ink-100 bg-ink-50/50">
              <tr>
                <th className="table-th">Name</th>
                <th className="table-th">Email</th>
                <th className="table-th">Role</th>
                <th className="table-th">Created</th>
                <th className="table-th text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-100">
              {users.map((u) => (
                <tr key={u.id} className="hover:bg-ink-50/60">
                  <td className="table-td font-medium text-ink-900">{u.name}</td>
                  <td className="table-td text-ink-600">{u.email}</td>
                  <td className="table-td">
                    <RoleBadge role={u.role} />
                  </td>
                  <td className="table-td text-ink-500">
                    {new Date(u.created_at).toLocaleDateString()}
                  </td>
                  <td className="table-td text-right">
                    <div className="flex justify-end gap-1">
                      <button className="btn-ghost px-2 py-1.5 text-sm" onClick={() => openEdit(u)}>
                        Edit
                      </button>
                      {u.id !== currentUser?.id && (
                        <button
                          className="btn-ghost px-2 py-1.5 text-sm text-red-600 hover:bg-red-50"
                          onClick={() => deleteUser(u)}
                        >
                          Delete
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal
        open={showCreate}
        onClose={closeModals}
        title="Add user"
        footer={
          <>
            <button className="btn-secondary" onClick={closeModals}>
              Cancel
            </button>
            <button className="btn-primary" onClick={createUser} disabled={saving}>
              {saving && <Spinner className="h-4 w-4 border-white/40 border-t-white" />}
              Create
            </button>
          </>
        }
      >
        <form onSubmit={createUser} className="space-y-4">
          <Field label="Name">
            <input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
          </Field>
          <Field label="Email">
            <input type="email" className="input" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required />
          </Field>
          <Field label="Password">
            <input type="password" className="input" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required />
          </Field>
          <div>
            <label className="label">Role</label>
            <select className="input" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
              <option value="user">User</option>
              <option value="admin">Admin</option>
            </select>
            <p className="mt-1 text-xs text-ink-400">
              Admins can manage settings, users, and Apollo enrichment.
            </p>
          </div>
        </form>
      </Modal>

      <Modal
        open={!!editUser}
        onClose={closeModals}
        title="Edit user"
        footer={
          <>
            <button className="btn-secondary" onClick={closeModals}>
              Cancel
            </button>
            <button className="btn-primary" onClick={updateUser} disabled={saving}>
              {saving && <Spinner className="h-4 w-4 border-white/40 border-t-white" />}
              Save
            </button>
          </>
        }
      >
        <form onSubmit={updateUser} className="space-y-4">
          <Field label="Name">
            <input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
          </Field>
          <Field label="Email">
            <input type="email" className="input" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required />
          </Field>
          <Field label="New password">
            <input
              type="password"
              className="input"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              placeholder="Leave blank to keep current"
            />
          </Field>
          <div>
            <label className="label">Role</label>
            <select
              className="input"
              value={form.role}
              onChange={(e) => setForm({ ...form, role: e.target.value })}
              disabled={editUser?.id === currentUser?.id}
            >
              <option value="user">User</option>
              <option value="admin">Admin</option>
            </select>
          </div>
        </form>
      </Modal>
    </div>
  );
}
