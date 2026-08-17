package com.ragguard.orchestrator.config;

import com.ragguard.orchestrator.model.Permission;
import com.ragguard.orchestrator.model.User;
import com.ragguard.orchestrator.repository.PermissionRepository;
import com.ragguard.orchestrator.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.CommandLineRunner;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.util.HashSet;
import java.util.Set;

@Component
@RequiredArgsConstructor
@Slf4j
public class DataInitializer implements CommandLineRunner {

    private final UserRepository userRepository;
    private final PermissionRepository permissionRepository;
    private final PasswordEncoder passwordEncoder;

    @Override
    @Transactional
    public void run(String... args) {
        initPermissions();
        initUsers();
    }

    private void initPermissions() {
        String[][] permissions = {
                {"documents:read", "Read documents", "documents", "read"},
                {"documents:write", "Write documents", "documents", "write"},
                {"documents:delete", "Delete documents", "documents", "delete"},
                {"documents:admin", "Admin documents", "documents", "admin"},
                {"chat:read", "Read chat", "chat", "read"},
                {"chat:write", "Write chat", "chat", "write"},
                {"policy:read", "Read policy", "policy", "read"},
                {"policy:write", "Write policy", "policy", "write"},
                {"security:read", "Read security", "security", "read"},
                {"security:admin", "Admin security", "security", "admin"},
                {"admin:all", "Full admin access", "admin", "all"}
        };

        for (String[] perm : permissions) {
            if (!permissionRepository.existsByName(perm[0])) {
                Permission permission = Permission.builder()
                        .name(perm[0])
                        .description(perm[1])
                        .resource(perm[2])
                        .action(perm[3])
                        .build();
                permissionRepository.save(permission);
            }
        }
    }

    private void initUsers() {
        // Create admin user
        if (!userRepository.existsByUsername("admin")) {
            Set<Permission> adminPerms = new HashSet<>(permissionRepository.findAll());

            User admin = User.builder()
                    .username("admin")
                    .passwordHash(passwordEncoder.encode("admin123"))
                    .role("ADMIN")
                    .department("IT")
                    .active(true)
                    .permissions(adminPerms)
                    .build();
            userRepository.save(admin);
            log.info("Created admin user");
        }

        // Create analyst user
        if (!userRepository.existsByUsername("analyst")) {
            Set<Permission> analystPerms = permissionRepository.findAll().stream()
                    .filter(p -> !p.getName().startsWith("admin:") && !p.getName().contains("security:admin"))
                    .collect(java.util.stream.Collectors.toSet());

            User analyst = User.builder()
                    .username("analyst")
                    .passwordHash(passwordEncoder.encode("analyst123"))
                    .role("ANALYST")
                    .department("Security")
                    .active(true)
                    .permissions(analystPerms)
                    .build();
            userRepository.save(analyst);
            log.info("Created analyst user");
        }

        // Create regular user
        if (!userRepository.existsByUsername("user")) {
            Set<Permission> userPerms = permissionRepository.findAll().stream()
                    .filter(p -> p.getAction().equals("read") || p.getName().equals("chat:write"))
                    .collect(java.util.stream.Collectors.toSet());

            User user = User.builder()
                    .username("user")
                    .passwordHash(passwordEncoder.encode("user123"))
                    .role("USER")
                    .department("Engineering")
                    .active(true)
                    .permissions(userPerms)
                    .build();
            userRepository.save(user);
            log.info("Created regular user");
        }
    }
}