using CleanCore.Application.Common.Interfaces;
using CleanCore.Domain.Common;
using CleanCore.Domain.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace CleanCore.Infrastructure.Persistence;

public sealed class ApplicationDbContext(DbContextOptions<ApplicationDbContext> options)
    : DbContext(options), IApplicationDbContext
{
    public DbSet<User> Users => Set<User>();

    public DbSet<RefreshToken> RefreshTokens => Set<RefreshToken>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<User>(builder =>
        {
            builder.ToTable("users");
            ConfigureBaseEntity(builder);

            builder.Property(user => user.Email)
                .HasMaxLength(256)
                .IsRequired();

            builder.HasIndex(user => user.Email)
                .IsUnique();

            builder.Property(user => user.PasswordHash)
                .HasMaxLength(128)
                .IsRequired();

            builder.Property(user => user.FirstName)
                .HasMaxLength(100)
                .IsRequired();

            builder.Property(user => user.LastName)
                .HasMaxLength(100)
                .IsRequired();

            builder.Property(user => user.Role)
                .HasConversion<string>()
                .HasMaxLength(32)
                .IsRequired();

            builder.HasMany(user => user.RefreshTokens)
                .WithOne()
                .HasForeignKey(token => token.UserId)
                .OnDelete(DeleteBehavior.Cascade);
        });

        modelBuilder.Entity<RefreshToken>(builder =>
        {
            builder.ToTable("refresh_tokens");
            ConfigureBaseEntity(builder);
            builder.Ignore(token => token.IsActive);

            builder.Property(token => token.Token)
                .HasMaxLength(128)
                .IsRequired();

            builder.HasIndex(token => token.Token)
                .IsUnique();

            builder.Property(token => token.ExpiresOnUtc)
                .IsRequired();
        });
    }

    private static void ConfigureBaseEntity<TEntity>(EntityTypeBuilder<TEntity> builder)
        where TEntity : BaseEntity
    {
        builder.HasKey(entity => entity.Id);

        builder.Property(entity => entity.CreatedAtUtc)
            .IsRequired();
    }
}
