import { Component, Input } from '@angular/core';
import { RouterModule } from '@angular/router';

// Material UI
import { MatIconModule } from '@angular/material/icon';
import { MatListModule } from '@angular/material/list';
import { MatSidenavModule } from '@angular/material/sidenav';
import { MatToolbarModule } from '@angular/material/toolbar';

// Local files 
import { Auth } from '../../services/auth/auth';

export interface MenuItem {
  label:      string;
  link:       string;
  permission: string;
}

@Component({
  selector: 'lib-default-layout',
  imports: [
    RouterModule,
    MatIconModule,
    MatListModule,
    MatSidenavModule,
    MatToolbarModule
  ],
  templateUrl: './default-layout.html',
  styleUrl: './default-layout.css'
})
export class DefaultLayout {
  @Input() navMenuItems: MenuItem[] = [];
  @Input() appTitle = "Shell App";

  constructor(public auth: Auth) {}

  // Only return menu items for which the user has permission
  get visibleMenuItems() {
    return this.navMenuItems.filter(item => this.auth.isAllowed([item.permission]));
  }
}
