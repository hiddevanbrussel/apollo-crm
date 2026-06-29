import { Field } from "./ui";

export default function ApolloFilterForm({ fields, values, onChange }) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {fields.map((field) => (
        <Field
          key={field.key}
          label={field.label}
          hint={field.hint}
        >
          {field.type === "boolean" ? (
            <select
              className="input"
              value={values[field.key] ?? ""}
              onChange={(e) => onChange(field.key, e.target.value)}
            >
              <option value="">Default (true)</option>
              <option value="true">Yes</option>
              <option value="false">No</option>
            </select>
          ) : (
            <input
              className="input"
              type={field.type === "number" ? "number" : field.type === "date" ? "date" : "text"}
              placeholder={field.placeholder}
              value={values[field.key] ?? ""}
              onChange={(e) => onChange(field.key, e.target.value)}
            />
          )}
        </Field>
      ))}
    </div>
  );
}
