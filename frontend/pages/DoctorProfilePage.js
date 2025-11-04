export default {
  template: `
  <div class="row">
    <div class="col-md-6 offset-md-3">
      <h3 class="text-center mb-3">Doctor Profile</h3>

      <!-- Flash Messages -->
      <div v-if="messages.length" class="mb-3">
        <div
          v-for="(message, index) in messages"
          :key="index"
          :class="'alert alert-' + message.category"
        >
          {{ message.text }}
        </div>
      </div>

      <!-- Profile Form -->
      <form @submit.prevent="submitForm">
        <div class="form-group mb-2">
          <label for="username">Username</label>
          <input
            id="username"
            v-model="form.username"
            type="text"
            class="form-control"
            readonly
          />
        </div>

        <div class="form-group mb-2">
          <label for="specialization">Specialization</label>
          <select
            id="specialization"
            v-model="form.specialization_id"
            class="form-control"
            required
          >
            <option disabled value="">Select a specialization</option>
            <option v-for="spec in specializationOptions" :key="spec.id" :value="spec.id">
              {{ spec.name }}
            </option>
          </select>
        </div>

        <div class="form-group mb-2">
          <label for="experience">Experience (Years)</label>
          <input
            id="experience"
            v-model="form.experience"
            type="number"
            min="0"
            class="form-control"
            required
          />
        </div>

        <div class="form-group mb-2">
          <label for="availability">Availability</label>
          <textarea
            id="availability"
            v-model="form.availability"
            class="form-control"
            placeholder="e.g. Mon–Fri, 10 AM – 4 PM"
          ></textarea>
        </div>

        <div class="form-group text-center mt-3">
          <button type="submit" class="btn btn-primary btn-sm px-4">Save</button>
        </div>
      </form>
    </div>
  </div>
  `,

  data() {
    return {
      form: {
        username: "",
        specialization_id: "",
        experience: "",
        availability: "",
      },
      specializationOptions: [],
      messages: [],
    };
  },

  mounted() {
    this.fetchProfileData();
    this.fetchSpecializations();
  },

  methods: {
    // Fetch current doctor profile
    async fetchProfileData() {
      this.messages = [];
      try {
        const res = await fetch(`${location.origin}/doctor/profile`, {
          method: "GET",
          headers: {
            Authorization: "Bearer " + localStorage.getItem("token"),
          },
        });

        if (res.ok) {
          const data = await res.json();
          if (data.message === "no profile") {
            this.messages.push({
              category: "info",
              text: "No profile found. Please fill out your details below.",
            });
            return;
          }
          this.form.username = data.username || localStorage.getItem("username") || "";
          this.form.specialization_id = data.specialization_id || "";
          this.form.experience = data.experience || "";
          this.form.availability = data.availability || "";
        } else {
          const err = await res.json();
          this.messages.push({
            category: err.category || "danger",
            text: err.message || "Failed to load profile data.",
          });
        }
      } catch (error) {
        console.error(error);
        this.messages.push({
          category: "danger",
          text: "An unexpected error occurred while loading your profile.",
        });
      }
    },

    // Fetch list of departments/specializations for dropdown
    async fetchSpecializations() {
      try {
        const res = await fetch(`${location.origin}/departments`);
        if (res.ok) {
          const data = await res.json();
          this.specializationOptions = data;
        }
      } catch (error) {
        console.error("Error loading specializations:", error);
      }
    },

    // Submit profile form
    async submitForm() {
      this.messages = [];
      try {
        const res = await fetch(`${location.origin}/doctor/profile`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: "Bearer " + localStorage.getItem("token"),
          },
          body: JSON.stringify(this.form),
        });

        const data = await res.json();
        if (res.ok) {
          this.messages.push({
            category: "success",
            text: data.message || "Profile saved successfully.",
          });
        } else {
          this.messages.push({
            category: "danger",
            text: data.message || "Failed to save profile.",
          });
        }
      } catch (error) {
        console.error(error);
        this.messages.push({
          category: "danger",
          text: "Network error occurred while saving profile.",
        });
      }
    },
  },
};
