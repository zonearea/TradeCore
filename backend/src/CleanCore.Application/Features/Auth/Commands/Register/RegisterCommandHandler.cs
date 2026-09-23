using CleanCore.Application.Common.Interfaces;
using CleanCore.Domain.Common;
using CleanCore.Domain.Entities;
using CleanCore.Domain.Errors;
using MediatR;
using Microsoft.EntityFrameworkCore;

namespace CleanCore.Application.Features.Auth.Commands.Register;

public sealed class RegisterCommandHandler(
    IApplicationDbContext dbContext,
    IPasswordHasher passwordHasher)
    : IRequestHandler<RegisterCommand, Result<Guid>>
{
    public async Task<Result<Guid>> Handle(RegisterCommand request, CancellationToken cancellationToken)
    {
        var email = request.Email.Trim().ToLowerInvariant();
        var emailInUse = await dbContext.Users.AnyAsync(
            user => user.Email == email,
            cancellationToken);

        if (emailInUse)
        {
            return Result.Failure<Guid>(UserErrors.EmailAlreadyInUse);
        }

        var user = new User
        {
            Id = Guid.NewGuid(),
            Email = email,
            PasswordHash = passwordHasher.Hash(request.Password),
            FirstName = request.FirstName.Trim(),
            LastName = request.LastName.Trim(),
            Role = Role.User,
            CreatedAtUtc = DateTime.UtcNow
        };

        dbContext.Users.Add(user);
        await dbContext.SaveChangesAsync(cancellationToken);

        return Result.Success(user.Id);
    }
}
