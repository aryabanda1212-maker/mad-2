export default {
  props: {
    id: {
      type: [String, Number],
      required: true
    }
  },

  data() {
    return {
      doctor: null,
      profile: null,
      message: null,
      category: null
    };
  },

  async created() {
    await this.fetchDoctorData();
  },

  methods: {
    async fetchDoctorData() {
      try {
        const res = await fetch(`${location.origin}/admin/doctors/${this.id}`, {
          headers: {
            'Authorization': 'Bearer ' + localStorage.getItem('token')
          }
        });
        if (res.ok) {
          const data = await res.json();
          this.doctor = data;
          this.profile = data.profile;
        } else {
          const err = await res.json();
          this.message = err.message || "Failed to load doctor data";
          this.category = "danger";
        }
      } catch (error) {
        this.message = "An error occurred while fetching doctor data.";
        this.category = "danger";
      }
    },

    async updateDoctor() {
      try {
        const res = await fetch(`${location.origin}/admin/doctors/${this.id}`, {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + localStorage.getItem('token')
          },
          body: JSON.stringify({
            approve: this.doctor.approve,
            blocked: this.doctor.blocked
          })
        });

        if (res.ok) {
          const data = await res.json();
          this.message = "Doctor updated successfully!";
          this.category = "success";
        } else {
          const err = await res.json();
          this.message = err.message || "Error updating doctor";
          this.category = "danger";
        }
      } catch (error) {
        this.message = "Unexpected error while updating doctor.";
        this.category = "danger";
      }
    },

    async deleteDoctor() {
      const confirmed = confirm("Are you sure you want to delete this doctor?");
      if (!confirmed) return;
      try {
        const res = await fetch(`${location.origin}/admin/doctors/${this.id}`, {
          method: 'DELETE',
          headers: {
            'Authorization': 'Bearer ' + localStorage.getItem('token')
          }
        });
        if (res.ok) {
          alert("Doctor deleted successfully!");
          this.$router.push('/admin/dashboard');
        } else {
          const err = await res.json();
          alert(err.message || "Failed to delete doctor.");
        }
      } catch (error) {
        alert("Error deleting doctor.");
      }
    }
  },

  template: `
  <div class="container mt-4" v-if="doctor">
    <h3>Edit Doctor Details</h3>

    <div v-if="message" :class="'alert alert-' + category" role="alert">{{ message }}</div>

    <table class="table table-bordered">
      <tr><th>ID</th><td>{{ doctor.id }}</td></tr>
      <tr><th>Username</th><td>{{ doctor.username }}</td></tr>
      <tr><th>Approved</th>
        <td>
          <input type="checkbox" v-model="doctor.approve" />
        </td>
      </tr>
      <tr><th>Blocked</th>
        <td>
          <input type="checkbox" v-model="doctor.blocked" />
        </td>
      </tr>
    </table>

    <div v-if="profile">
      <h4>Profile Information</h4>
      <table class="table table-bordered">
        <tr><th>Specialization</th><td>{{ profile.specialization_id || '—' }}</td></tr>
        <tr><th>Experience</th><td>{{ profile.experience || '—' }}</td></tr>
        <tr><th>Availability</th><td>{{ profile.availability || '—' }}</td></tr>
      </table>
    </div>

    <div class="text-center mt-4">
      <button @click="updateDoctor" class="btn btn-primary me-2">Save Changes</button>
      <button @click="deleteDoctor" class="btn btn-danger me-2">Delete Doctor</button>
      <router-link to="/admin/dashboard" class="btn btn-secondary">Cancel</router-link>
    </div>
  </div>

  <div v-else class="text-center mt-5">
    <h4>Loading doctor details...</h4>
  </div>
  `
};
