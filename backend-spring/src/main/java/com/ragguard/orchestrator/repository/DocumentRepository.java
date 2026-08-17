package com.ragguard.orchestrator.repository;

import com.ragguard.orchestrator.model.Document;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface DocumentRepository extends JpaRepository<Document, Long> {

    List<Document> findByOwnerId(Long ownerId);

    List<Document> findByDepartment(String department);

    List<Document> findByClassificationLevel(String classificationLevel);

    Page<Document> findByOwnerId(Long ownerId, Pageable pageable);

    Page<Document> findByDepartment(String department, Pageable pageable);

    @Query("SELECT d FROM Document d WHERE d.ownerId = :ownerId OR d.department = :department")
    Page<Document> findAccessibleDocuments(@Param("ownerId") Long ownerId, @Param("department") String department, Pageable pageable);

    List<Document> findByStatus(String status);

    Optional<Document> findByIdAndOwnerId(Long id, Long ownerId);
}