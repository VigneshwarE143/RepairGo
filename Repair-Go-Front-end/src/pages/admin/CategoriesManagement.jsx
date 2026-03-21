import { useState, useEffect } from "react";
import { useForm } from "react-hook-form";
import toast from "react-hot-toast";
import { adminAPI } from "../../services/api";

const CATEGORY_ICONS = {
  plumbing: "🔧",
  electrical: "⚡",
  hvac: "❄️",
  appliance: "🔌",
  cleaning: "🧹",
  painting: "🎨",
  carpentry: "🪚",
  general: "🛠️",
};

export default function CategoriesManagement() {
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingCategory, setEditingCategory] = useState(null);
  const [deleteModal, setDeleteModal] = useState({
    show: false,
    category: null,
  });

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    formState: { errors },
  } = useForm();

  useEffect(() => {
    loadCategories();
  }, []);

  const loadCategories = async () => {
    setLoading(true);
    try {
      const response = await adminAPI.getCategories();
      setCategories(response.data || []);
    } catch (error) {
      // If API doesn't exist, use default categories
      setCategories([
        {
          _id: "1",
          name: "plumbing",
          base_price: 50,
          description: "Plumbing repairs and installations",
        },
        {
          _id: "2",
          name: "electrical",
          base_price: 60,
          description: "Electrical work and repairs",
        },
        {
          _id: "3",
          name: "hvac",
          base_price: 75,
          description: "Heating, ventilation, air conditioning",
        },
        {
          _id: "4",
          name: "appliance",
          base_price: 45,
          description: "Appliance repairs",
        },
        {
          _id: "5",
          name: "cleaning",
          base_price: 30,
          description: "Professional cleaning services",
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const openCreateModal = () => {
    setEditingCategory(null);
    reset({ name: "", base_price: "", description: "" });
    setShowModal(true);
  };

  const openEditModal = (category) => {
    setEditingCategory(category);
    setValue("name", category.name);
    setValue("base_price", category.base_price);
    setValue("description", category.description || "");
    setShowModal(true);
  };

  const onSubmit = async (data) => {
    try {
      if (editingCategory) {
        await adminAPI.updateCategory(editingCategory._id, data);
        toast.success("Category updated");
      } else {
        await adminAPI.createCategory(data);
        toast.success("Category created");
      }
      setShowModal(false);
      loadCategories();
    } catch (error) {
      toast.error(error.message || "Operation failed");
    }
  };

  const handleDelete = async () => {
    try {
      await adminAPI.deleteCategory(deleteModal.category._id);
      toast.success("Category deleted");
      setDeleteModal({ show: false, category: null });
      loadCategories();
    } catch (error) {
      toast.error("Failed to delete category");
    }
  };

  if (loading) {
    return (
      <div className="loading-page">
        <div className="loading-spinner lg"></div>
      </div>
    );
  }

  return (
    <div>
      <div className="page-header">
        <h1>Categories Management</h1>
        <p>Manage service categories and pricing</p>
        <div className="page-header-actions">
          <button className="btn btn-primary" onClick={openCreateModal}>
            + Add Category
          </button>
        </div>
      </div>

      {/* Categories Grid */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))",
          gap: "24px",
        }}
      >
        {categories.map((category) => (
          <div key={category._id} className="card">
            <div className="card-body">
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "flex-start",
                }}
              >
                <div
                  style={{ display: "flex", alignItems: "center", gap: "12px" }}
                >
                  <div
                    style={{
                      width: 48,
                      height: 48,
                      borderRadius: "12px",
                      background: "var(--primary-light)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: "1.5rem",
                    }}
                  >
                    {CATEGORY_ICONS[category.name] || "🛠️"}
                  </div>
                  <div>
                    <h3
                      style={{
                        textTransform: "capitalize",
                        marginBottom: "4px",
                      }}
                    >
                      {category.name}
                    </h3>
                    <span className="badge badge-success">
                      ${category.base_price?.toFixed(2)} base
                    </span>
                  </div>
                </div>
              </div>

              {category.description && (
                <p className="text-muted text-sm" style={{ marginTop: "16px" }}>
                  {category.description}
                </p>
              )}

              <div style={{ display: "flex", gap: "8px", marginTop: "16px" }}>
                <button
                  className="btn btn-outline btn-sm"
                  onClick={() => openEditModal(category)}
                  style={{ flex: 1 }}
                >
                  ✏️ Edit
                </button>
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={() => setDeleteModal({ show: true, category })}
                  style={{ color: "var(--danger)" }}
                >
                  🗑️
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {categories.length === 0 && (
        <div className="card">
          <div className="empty-state">
            <div className="empty-state-icon">📁</div>
            <h3>No Categories</h3>
            <p>Create your first service category to get started.</p>
            <button className="btn btn-primary mt-4" onClick={openCreateModal}>
              + Add Category
            </button>
          </div>
        </div>
      )}

      {/* Create/Edit Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">
                {editingCategory ? "Edit Category" : "Create Category"}
              </h3>
              <button
                className="modal-close"
                onClick={() => setShowModal(false)}
              >
                ×
              </button>
            </div>
            <form onSubmit={handleSubmit(onSubmit)}>
              <div className="modal-body">
                <div className="form-group">
                  <label className="form-label">Category Name</label>
                  <input
                    type="text"
                    className={`form-input ${errors.name ? "error" : ""}`}
                    placeholder="e.g., plumbing"
                    {...register("name", { required: "Name is required" })}
                  />
                  {errors.name && (
                    <span className="form-error">{errors.name.message}</span>
                  )}
                </div>

                <div className="form-group">
                  <label className="form-label">Base Price ($)</label>
                  <input
                    type="number"
                    step="0.01"
                    className={`form-input ${errors.base_price ? "error" : ""}`}
                    placeholder="50.00"
                    {...register("base_price", {
                      required: "Base price is required",
                      min: { value: 0, message: "Must be positive" },
                    })}
                  />
                  {errors.base_price && (
                    <span className="form-error">
                      {errors.base_price.message}
                    </span>
                  )}
                </div>

                <div className="form-group">
                  <label className="form-label">Description</label>
                  <textarea
                    className="form-textarea"
                    rows="3"
                    placeholder="Describe this service category..."
                    {...register("description")}
                  ></textarea>
                </div>
              </div>
              <div className="modal-footer">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setShowModal(false)}
                >
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  {editingCategory ? "Update" : "Create"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Modal */}
      {deleteModal.show && (
        <div
          className="modal-overlay"
          onClick={() => setDeleteModal({ show: false, category: null })}
        >
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">Delete Category</h3>
              <button
                className="modal-close"
                onClick={() => setDeleteModal({ show: false, category: null })}
              >
                ×
              </button>
            </div>
            <div className="modal-body">
              <div className="alert alert-danger">
                <span className="alert-icon">⚠️</span>
                <div className="alert-content">
                  <strong>Warning</strong>
                  <p>Deleting a category may affect existing jobs.</p>
                </div>
              </div>
              <p style={{ marginTop: "16px" }}>
                Are you sure you want to delete{" "}
                <strong style={{ textTransform: "capitalize" }}>
                  {deleteModal.category?.name}
                </strong>
                ?
              </p>
            </div>
            <div className="modal-footer">
              <button
                className="btn btn-secondary"
                onClick={() => setDeleteModal({ show: false, category: null })}
              >
                Cancel
              </button>
              <button className="btn btn-danger" onClick={handleDelete}>
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
