import { Component, Input, OnInit } from '@angular/core';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { Router } from '@angular/router';

import { Auth } from '../../services/auth/auth'

@Component({
  selector: 'lib-profile',
  imports: [
    ReactiveFormsModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatCardModule
  ],
  templateUrl: './profile.html',
  styleUrl: './profile.css'
})
export class Profile {
  @Input() userId!: string; // pass the user's ID from parent
  @Input() currentEmail!: string;
  @Input() currentUsername!: string;

  form: FormGroup;
  loading = false;

  constructor(
    private fb: FormBuilder,
    private http: HttpClient,
    private auth: Auth,
    private router: Router
  ) {
    this.form = this.fb.group({
      email: ['', [Validators.required, Validators.email]],
      userName: ['', Validators.required]
    });
  }

  ngOnInit(): void {
    // Pre-fill form with existing data
    this.form.patchValue({
      email: this.currentEmail,
      userName: this.currentUsername
    });
  }

  onSubmit(): void {
    if (this.form.invalid) return;
    this.loading = true;

    const formData = new FormData();
    formData.append('email', this.form.value.email);
    formData.append('username', this.form.value.userName);

    this.http.put(`/api/v1/user`, formData, {
      headers: {
        Authorization: `Bearer ${this.auth.token}`
      },
      observe: 'response'
    }).subscribe({
      next: (res) => {
        if (res.status === 204) {
          this.router.navigate(['/profile']);
        }
        this.loading = false;
      },
      error: (err) => {
        console.error('Update failed', err);
        this.loading = false;
      }
    });
  }
}
