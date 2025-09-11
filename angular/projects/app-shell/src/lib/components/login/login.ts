import { Component } from '@angular/core';
import { Router, RouterModule } from '@angular/router';

/** Form & Materials */
import { ReactiveFormsModule, FormBuilder, FormGroup, Validators } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';

/** Local files */
import { Auth } from '../../services/auth/auth'

@Component({
  selector: 'lib-login',
  imports: [
    ReactiveFormsModule, 
    MatCardModule,
    MatFormFieldModule, 
    MatInputModule,
    MatButtonModule,
    RouterModule
  ],
  templateUrl: './login.html',
  styleUrl: './login.css'
})
export class Login {
  loginForm: FormGroup;
  error: string | null = null;

  constructor(
    private fb: FormBuilder, 
    private router: Router,
    private auth: Auth
  ) {
    this.loginForm = this.fb.group({
      email: ['', [Validators.required, Validators.email]],
      password: ['', Validators.required],
    });
  }

  onSubmit() {
    if (this.loginForm.invalid) return;

    const { email, password } = this.loginForm.value;

    // Placeholder authentication logic
    this.auth.login(email, password).subscribe({
      next: () => this.router.navigate(['/']),
      error: (err) => {
        console.error(err)
        this.error = 'Login failed. Please check your credentials.'
      }
    })
  }
}
