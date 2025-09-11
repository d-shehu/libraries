import { Component, ViewChild } from '@angular/core';
import { CommonModule, NgClass } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { MatChipsModule } from '@angular/material/chips';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatSort, MatSortModule } from '@angular/material/sort';
import { MatTableDataSource, MatTableModule } from '@angular/material/table';

import { Auth } from '../../services/auth/auth'

interface User {
  id:       string
  email:    string
  username: string
  isActive: boolean
}

@Component({
  selector: 'lib-user-mgmt',
  imports: [
    CommonModule,
    MatChipsModule,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    MatProgressSpinnerModule,
    MatSnackBarModule,
    MatSortModule,
    MatTableModule
  ],
  templateUrl: './user-mgmt.html',
  styleUrl: './user-mgmt.css'
})
export class UserMgmt {
  displayedColumns: string[] = ['id', 'username', 'email', 'isActive'];
  dataSource: MatTableDataSource<User> = new MatTableDataSource<User>();
  loading = true;
  currentUserID: string | null = null;

  @ViewChild(MatSort) sort!: MatSort;

  constructor(
    private http: HttpClient,
    private auth: Auth,
    private snackBar: MatSnackBar
  ) { }

  ngOnInit(): void {
    this.currentUserID = this.auth.getUserID();
    // Fetch all users
    this.fetchUsers()
  }

  fetchUsers(): void {
    this.http.get<User[]>('/api/v1/users', {
      headers: {
        Authorization: `Bearer ${this.auth.token}`
      }
    }).subscribe({
      next: (data) => {
        this.dataSource.data = data;
        this.dataSource.sort = this.sort;
        this.loading = false;
      },
      error: (err) => {
        console.error('Failed to fetch users', err);
        this.loading = false;
      }
    });
  }

  applyFilter(event: Event): void {
    const filterValue = (event.target as HTMLInputElement).value.trim().toLowerCase();
    this.dataSource.filter = filterValue;
    this.dataSource.filterPredicate = (data, filter) =>
      data.email.toLowerCase().includes(filter) ||
      data.username.toLowerCase().includes(filter);
  }

  deactivateUser(user: User) {
    if (!confirm(`Deactivate user ${user.username}?`)) return;

    this.http.put(`/api/v1/users/${user.id}/deactivate`, {}, {
      headers: { Authorization: `Bearer ${this.auth.token}` },
      observe: 'response'
    }).subscribe({
      next: (res) => {
        if (res.status === 200 || res.status === 204) {
          this.snackBar.open('User deactivated', 'Close', { duration: 2000 });
          this.fetchUsers();
        }
      },
      error: (err) => {
        console.error(err);
        this.snackBar.open('Failed to deactivate user', 'Close', { duration: 3000 });
      }
    });
  }

  deleteUser(user: User) {
    if (!confirm(`Permanently delete user ${user.username}? This cannot be undone.`)) return;

    this.http.delete(`/api/v1/users/${user.id}`, {
      headers: { Authorization: `Bearer ${this.auth.token}` },
      observe: 'response'
    }).subscribe({
      next: (res) => {
        if (res.status === 204) {
          this.snackBar.open('User deleted', 'Close', { duration: 2000 });
          this.fetchUsers();
        }
      },
      error: (err) => {
        console.error(err);
        this.snackBar.open('Failed to delete user', 'Close', { duration: 3000 });
      }
    });
  }

  canModify(user: User) {
    // disable both deactivate and delete if current user
    return user.id !== this.currentUserID;
  }
}
